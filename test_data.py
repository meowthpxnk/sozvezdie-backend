#!/usr/bin/env python3
"""
Заполняет БД тестовыми авторами и товарами, скачивает изображения в директорию
и загружает их в MinIO.

Запуск из корня backend:
    python test_data.py
    python test_data.py --authors 100 --products 2000
    python test_data.py --clear
    python test_data.py --skip-download
"""

from __future__ import annotations

import argparse
import asyncio
import binascii
import hashlib
import os
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from app.core.redis_client import redis_client  # noqa: E402
from app.database import Database  # noqa: E402
from app.media_client import MediaClient  # noqa: E402
from app.models import (  # noqa: E402
    Inventory,
    Product,
    ProductImage,
    SellerCard,
    User,
    UserSettings,
)
from app.schemas.database import AppTheme, ModerationStatus, UserRoleEnum  # noqa: E402
from app.services.catalog_facet_cache import CatalogFacetCacheService  # noqa: E402
from app.settings import DatabaseSettings, MinioSettings  # noqa: E402

USERNAME_PREFIX = "test_author_"
DEFAULT_AUTHORS = 100
DEFAULT_PRODUCTS = 2000
PRODUCT_IMAGE_POOL = 200
AVATAR_POOL = 100
BANNER_POOL = 40
BATCH_SIZE = 50

CATEGORIES = [
    "gifts",
    "jewelry",
    "dolls",
    "stationery",
    "interior",
    "accessories",
    "wear",
    "cosmetics",
]

FANDOMS = [
    "naruto",
    "one-piece",
    "demon-slayer",
    "attack-on-titan",
    "genshin-impact",
    "marvel",
    "harry-potter",
    "star-wars",
    "minecraft",
    "original",
]

AUTHOR_NAME_PARTS = [
    "Астра",
    "Луна",
    "Нова",
    "Ирис",
    "Мира",
    "Сова",
    "Берри",
    "Кора",
    "Лайм",
    "Пикси",
    "Флора",
    "Вельвет",
    "Снежка",
    "Тинки",
    "Глицин",
    "Роза",
    "Сахар",
    "Мята",
    "Облако",
    "Зефир",
]

AUTHOR_SUFFIXES = [
    "Студия",
    "Мастерская",
    "Шоп",
    "Галерея",
    "Ателье",
    "Лавка",
    "Дом",
    "Крафт",
    "Арт",
    "Place",
]

PRODUCT_ADJECTIVES = [
    "авторский",
    "лимитированный",
    "ручной работы",
    "коллекционный",
    "подарочный",
    "премиальный",
    "уютный",
    "яркий",
    "нежный",
    "стильный",
]

PRODUCT_NOUNS = [
    "значок",
    "брелок",
    "постер",
    "стикерпак",
    "кружка",
    "блокнот",
    "фигурка",
    "браслет",
    "кольцо",
    "плед",
    "подушка",
    "свеча",
    "бокс",
    "пин",
    "артбук",
]


def hash_password(password: str) -> str:
    salt = hashlib.sha256(os.urandom(60)).hexdigest().encode("ascii")
    secret_hash = hashlib.pbkdf2_hmac(
        "sha512", password.encode("utf-8"), salt, 100000
    )
    return (salt + binascii.hexlify(secret_hash)).decode("ascii")


def picsum_url(seed: str, width: int, height: int) -> str:
    return f"https://picsum.photos/seed/{seed}/{width}/{height}"


async def download_file(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size > 0:
        return

    destination.parent.mkdir(parents=True, exist_ok=True)

    def _download() -> None:
        request = Request(
            url,
            headers={"User-Agent": "sozvezdie-test-data/1.0"},
        )
        with urlopen(request, timeout=60) as response:
            destination.write_bytes(response.read())

    await asyncio.to_thread(_download)


async def prepare_image_pool(
    images_dir: Path,
    pool_name: str,
    pool_size: int,
    width: int,
    height: int,
    skip_download: bool,
) -> list[Path]:
    folder = images_dir / pool_name
    folder.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    print(f"Изображения «{pool_name}»: {pool_size} файлов")
    for index in range(1, pool_size + 1):
        path = folder / f"{index:04d}.jpg"
        paths.append(path)
        if skip_download and not path.exists():
            raise FileNotFoundError(
                f"Нет файла {path}. Запустите без --skip-download."
            )
        if skip_download:
            continue

        seed = f"sozvezdie-{pool_name}-{index}"
        url = picsum_url(seed, width, height)
        try:
            await download_file(url, path)
        except URLError as error:
            raise RuntimeError(f"Не удалось скачать {url}") from error

        if index % 20 == 0 or index == pool_size:
            print(f"  скачано {index}/{pool_size}")

    return paths


async def upload_image_paths(
    media_client: MediaClient,
    paths: list[Path],
) -> list[str]:
    uuids: list[str] = []

    print(f"Загрузка в MinIO: {len(paths)} файлов")
    await media_client.ensure_bucket()

    for index, path in enumerate(paths, start=1):
        image_bytes = path.read_bytes()
        image_uuid = await media_client.upload_image(
            image_bytes=image_bytes,
            content_type="image/jpeg",
        )
        uuids.append(image_uuid)

        if index % 20 == 0 or index == len(paths):
            print(f"  загружено {index}/{len(paths)}")

    return uuids


def build_author_name(index: int) -> str:
    part = AUTHOR_NAME_PARTS[index % len(AUTHOR_NAME_PARTS)]
    suffix = AUTHOR_SUFFIXES[(index // len(AUTHOR_NAME_PARTS)) % len(AUTHOR_SUFFIXES)]
    return f"{part} {suffix}"


def build_product_name(index: int) -> str:
    adjective = PRODUCT_ADJECTIVES[index % len(PRODUCT_ADJECTIVES)]
    noun = PRODUCT_NOUNS[(index // len(PRODUCT_ADJECTIVES)) % len(PRODUCT_NOUNS)]
    return f"{adjective.capitalize()} {noun} #{index}"


async def clear_test_data(session: AsyncSession) -> None:
    result = await session.execute(
        select(User.id).where(User.username.like(f"{USERNAME_PREFIX}%"))
    )
    user_ids = [row[0] for row in result.all()]
    if not user_ids:
        print("Тестовые пользователи не найдены.")
        return

    await session.execute(delete(User).where(User.id.in_(user_ids)))
    await session.commit()
    print(f"Удалено тестовых пользователей: {len(user_ids)}")


async def seed_authors(
    session: AsyncSession,
    authors_count: int,
    avatar_uuids: list[str],
    banner_uuids: list[str],
) -> list[SellerCard]:
    existing = await session.execute(
        select(User.username).where(User.username.like(f"{USERNAME_PREFIX}%"))
    )
    if existing.first():
        raise RuntimeError(
            "Тестовые авторы уже существуют. Сначала выполните: python test_data.py --clear"
        )

    password_hash = hash_password("test_password")

    print(f"Создание авторов: {authors_count}")
    for index in range(1, authors_count + 1):
        username = f"{USERNAME_PREFIX}{index:03d}"
        user = User(
            username=username,
            password_hash=password_hash,
            role=UserRoleEnum.SELLER,
            full_name=build_author_name(index),
            email=f"{username}@example.com",
        )
        user.settings = UserSettings(theme=AppTheme.DARK)
        user.seller_card = SellerCard(
            name=build_author_name(index),
            desc=f"Тестовый автор каталога #{index}",
            avatar_image=avatar_uuids[(index - 1) % len(avatar_uuids)],
            banner_image=banner_uuids[(index - 1) % len(banner_uuids)],
        )
        session.add(user)

        if index % BATCH_SIZE == 0:
            await session.flush()
            print(f"  подготовлено {index}/{authors_count}")

    await session.flush()
    await session.commit()

    result = await session.execute(
        select(SellerCard)
        .join(User, SellerCard.user_id == User.id)
        .where(User.username.like(f"{USERNAME_PREFIX}%"))
        .order_by(SellerCard.id)
    )
    seller_cards = list(result.scalars().all())
    print(f"Авторы созданы: {len(seller_cards)}")
    return seller_cards


async def seed_products(
    session: AsyncSession,
    seller_cards: list[SellerCard],
    products_count: int,
    product_image_uuids: list[str],
) -> None:
    if not seller_cards:
        raise RuntimeError("Нет авторов для создания товаров.")

    print(f"Создание товаров: {products_count}")
    random_gen = random.Random(42)

    for index in range(1, products_count + 1):
        seller_card = seller_cards[(index - 1) % len(seller_cards)]
        images_count = random_gen.randint(1, 3)
        image_ids = random_gen.sample(
            product_image_uuids,
            k=min(images_count, len(product_image_uuids)),
        )

        product = Product(
            name=build_product_name(index),
            desc=(
                f"Тестовый товар #{index} для нагрузочного наполнения каталога. "
                f"Категория и фандом выбраны случайно."
            ),
            price=random_gen.randint(29900, 2_990_000),
            status=ModerationStatus.APPROVED,
            seller_card_id=seller_card.id,
            category_slug=random_gen.choice(CATEGORIES),
            fandom_slug=random_gen.choice(FANDOMS),
            created_at=datetime.now() - timedelta(minutes=products_count - index),
        )

        for image_order, image_uuid in enumerate(image_ids):
            product.images.append(
                ProductImage(
                    image_uuid=UUID(image_uuid),
                    order=image_order,
                )
            )

        product.inventory = Inventory(
            quantity=random_gen.randint(1, 120),
        )
        session.add(product)

        if index % BATCH_SIZE == 0:
            await session.flush()
            print(f"  создано {index}/{products_count}")

    await session.commit()
    print(f"Товары созданы: {products_count}")


async def ensure_catalog_reference_data(session: AsyncSession) -> None:
    from app.models import Category, Fandom

    categories = (
        await session.execute(select(Category.slug))
    ).scalars().all()
    fandoms = (await session.execute(select(Fandom.slug))).scalars().all()

    if not categories:
        raise RuntimeError(
            "В БД нет категорий. Сначала выполните: alembic upgrade head"
        )
    if not fandoms:
        raise RuntimeError(
            "В БД нет фандомов. Сначала выполните: alembic upgrade head"
        )


async def rebuild_facet_cache(session: AsyncSession) -> None:
    print("Пересборка Redis-кеша счётчиков каталога")
    cache = CatalogFacetCacheService(redis_client)
    await cache.rebuild(session)
    print("Кеш каталога обновлён")


async def run(args: argparse.Namespace) -> None:
    images_dir = Path(args.images_dir).resolve()
    database = Database(DatabaseSettings())
    media_client = MediaClient(MinioSettings().minio_uri)

    if args.clear:
        async with database.session() as session:
            await clear_test_data(session)
            await rebuild_facet_cache(session)
        await database.engine.dispose()
        await redis_client.aclose()
        return

    avatar_paths = await prepare_image_pool(
        images_dir,
        "avatars",
        AVATAR_POOL,
        512,
        512,
        args.skip_download,
    )
    banner_paths = await prepare_image_pool(
        images_dir,
        "banners",
        BANNER_POOL,
        1280,
        420,
        args.skip_download,
    )
    product_paths = await prepare_image_pool(
        images_dir,
        "products",
        PRODUCT_IMAGE_POOL,
        900,
        900,
        args.skip_download,
    )

    avatar_uuids = await upload_image_paths(media_client, avatar_paths)
    banner_uuids = await upload_image_paths(media_client, banner_paths)
    product_image_uuids = await upload_image_paths(media_client, product_paths)

    async with database.session() as session:
        await ensure_catalog_reference_data(session)

        seller_cards = await seed_authors(
            session,
            args.authors,
            avatar_uuids,
            banner_uuids,
        )
        await seed_products(
            session,
            seller_cards,
            args.products,
            product_image_uuids,
        )
        await rebuild_facet_cache(session)

    await database.engine.dispose()
    await redis_client.aclose()

    print()
    print("Готово.")
    print(f"  авторы:   {args.authors}")
    print(f"  товары:   {args.products}")
    print(f"  фото:     {images_dir}")
    print("  логин:    test_author_001")
    print("  пароль:   test_password")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Наполнение БД тестовыми авторами и товарами",
    )
    parser.add_argument(
        "--authors",
        type=int,
        default=DEFAULT_AUTHORS,
        help=f"Количество авторов (по умолчанию {DEFAULT_AUTHORS})",
    )
    parser.add_argument(
        "--products",
        type=int,
        default=DEFAULT_PRODUCTS,
        help=f"Количество товаров (по умолчанию {DEFAULT_PRODUCTS})",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=ROOT_DIR / "test_data_images",
        help="Директория для скачанных изображений",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Не скачивать изображения, использовать уже сохранённые файлы",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Удалить тестовых авторов и связанные данные",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.authors < 1:
        raise SystemExit("--authors должно быть >= 1")
    if args.products < 1 and not args.clear:
        raise SystemExit("--products должно быть >= 1")

    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nПрервано пользователем.")


if __name__ == "__main__":
    main()
