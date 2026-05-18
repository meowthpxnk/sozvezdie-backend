from sqlalchemy import and_, or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Inventory, Product, ProductModeration, SellerCard, Subcategory
from app.schemas.database import ModerationStatus

from .specs.product import ProductSpec


class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def _product_load_options(self, spec: ProductSpec):
        options = []
        if spec.include_images:
            options.append(selectinload(Product.images))
        if spec.include_inventory:
            options.append(selectinload(Product.inventory))
        if spec.include_seller_card:
            options.append(
                selectinload(Product.seller_card).selectinload(SellerCard.user)
            )
        if spec.include_subcategory:
            options.append(selectinload(Product.subcategory))
        if spec.include_moderations:
            options.append(
                selectinload(Product.moderations).selectinload(
                    ProductModeration.moderator
                )
            )
        return options

    async def list_for_moderation(
        self, status: ModerationStatus | None = None
    ) -> list[Product]:
        stmt = select(Product).order_by(Product.created_at.desc())
        if status is not None:
            stmt = stmt.where(Product.status == status)

        stmt = stmt.options(
            selectinload(Product.images),
            selectinload(Product.inventory),
            selectinload(Product.seller_card).selectinload(SellerCard.user),
            selectinload(Product.moderations).selectinload(
                ProductModeration.moderator
            ),
            selectinload(Product.subcategory),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_product_moderations_for_feed(
        self, status: ModerationStatus | None = None
    ) -> list[ProductModeration]:
        stmt = (
            select(ProductModeration)
            .join(Product)
            .where(Product.status == ModerationStatus.APPROVED)
            .order_by(ProductModeration.created_at.desc())
        )
        if status is not None:
            stmt = stmt.where(ProductModeration.status == status)

        stmt = stmt.options(
            selectinload(ProductModeration.product).selectinload(Product.images),
            selectinload(ProductModeration.product).selectinload(Product.inventory),
            selectinload(ProductModeration.product)
            .selectinload(Product.seller_card)
            .selectinload(SellerCard.user),
            selectinload(ProductModeration.moderator),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().unique().all())

    async def get_product(self, spec: ProductSpec):
        if (
            spec.id is None
            and spec.seller_card_id is None
            and not spec.ids
        ):
            raise ValueError("ProductSpec requires id, ids or authorId")

        stmt = select(Product)
        if spec.id is not None:
            stmt = stmt.where(Product.id == spec.id)
        if spec.ids:
            stmt = stmt.where(Product.id.in_(spec.ids))
        if spec.seller_card_id is not None:
            stmt = stmt.where(
                Product.seller_card_id == int(spec.seller_card_id)
            )
        if spec.approved_only:
            stmt = stmt.where(Product.status == ModerationStatus.APPROVED)
        stmt = stmt.options(*self._product_load_options(spec))

        result = await self.session.execute(stmt)
        if spec.all:
            return result.scalars().all()
        return result.scalar_one_or_none()

    async def get_all(
        self,
        category_slug: str | None = None,
        subcategory_slug: str | None = None,
        fandom_slug: str | None = None,
    ) -> list[Product]:
        stmt = select(Product)

        if subcategory_slug and category_slug:
            stmt = stmt.join(Subcategory).where(
                Subcategory.slug == subcategory_slug,
                Subcategory.category_slug == category_slug,
            )
        elif category_slug:
            stmt = stmt.where(Product.category_slug == category_slug)

        if fandom_slug:
            stmt = stmt.where(Product.fandom_slug == fandom_slug)

        stmt = self._apply_approved_filter(stmt)

        options = [
            selectinload(Product.images),
            selectinload(Product.inventory),
            selectinload(Product.seller_card),
            selectinload(Product.subcategory),
        ]
        stmt = stmt.options(*options).distinct()
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _apply_approved_filter(stmt):
        return stmt.where(Product.status == ModerationStatus.APPROVED)

    def _product_list_options(self):
        return [
            selectinload(Product.images),
            selectinload(Product.inventory),
            selectinload(Product.seller_card),
            selectinload(Product.subcategory),
        ]

    def _apply_product_filters(
        self,
        stmt,
        *,
        category_slug: str | None,
        subcategory_slug: str | None,
        fandom_slug: str | None,
    ):
        if subcategory_slug and category_slug:
            stmt = stmt.join(Subcategory).where(
                Subcategory.slug == subcategory_slug,
                Subcategory.category_slug == category_slug,
            )
        elif category_slug:
            stmt = stmt.where(Product.category_slug == category_slug)

        if fandom_slug:
            stmt = stmt.where(Product.fandom_slug == fandom_slug)

        return stmt

    @staticmethod
    def _escape_ilike_prefix(value: str) -> str:
        escaped = (
            value.replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )
        return f"{escaped}%"

    def _apply_starts_with_filter(self, stmt, starts_with: str | None):
        if not starts_with or not starts_with.strip():
            return stmt

        pattern = self._escape_ilike_prefix(starts_with.strip())
        stmt = stmt.join(SellerCard, Product.seller_card_id == SellerCard.id)
        return stmt.where(
            or_(
                Product.name.ilike(pattern, escape="\\"),
                SellerCard.name.ilike(pattern, escape="\\"),
            )
        )

    async def get_similar_pool(
        self,
        *,
        product_id: int,
        fandom_slug: str | None,
        subcategory_id: int | None,
        category_slug: str | None,
        pool_limit: int = 100,
    ) -> list[Product]:
        pool_limit = max(1, min(pool_limit, 100))
        stmt = select(Product)
        stmt = self._apply_approved_filter(stmt)
        stmt = stmt.where(Product.id != product_id)

        conditions = []
        if fandom_slug:
            conditions.append(Product.fandom_slug == fandom_slug)
        if subcategory_id is not None:
            conditions.append(Product.subcategory_id == subcategory_id)
        if category_slug:
            conditions.append(Product.category_slug == category_slug)

        if conditions:
            stmt = stmt.where(or_(*conditions))

        stmt = (
            stmt.options(*self._product_list_options())
            .order_by(Product.created_at.desc(), Product.id.desc())
            .limit(pool_limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_page(
        self,
        *,
        category_slug: str | None = None,
        subcategory_slug: str | None = None,
        fandom_slug: str | None = None,
        limit: int = 20,
        after_id: int | None = None,
        sort: str = "popular",
        starts_with: str | None = None,
    ) -> tuple[list[Product], bool]:
        limit = max(1, min(limit, 100))
        stmt = select(Product)
        stmt = self._apply_product_filters(
            stmt,
            category_slug=category_slug,
            subcategory_slug=subcategory_slug,
            fandom_slug=fandom_slug,
        )
        stmt = self._apply_starts_with_filter(stmt, starts_with)
        stmt = self._apply_approved_filter(stmt)

        if sort == "popular":
            stmt = stmt.join(Inventory, Product.inventory)

        if after_id is not None:
            if sort in {"newest", "oldest"}:
                cursor_product = await self.get_product(
                    ProductSpec(id=after_id, approved_only=True)
                )
                if cursor_product is None:
                    return [], False

                cursor_created_at = cursor_product.created_at
                if sort == "newest":
                    stmt = stmt.where(
                        or_(
                            Product.created_at < cursor_created_at,
                            and_(
                                Product.created_at == cursor_created_at,
                                Product.id < after_id,
                            ),
                        )
                    )
                else:
                    stmt = stmt.where(
                        or_(
                            Product.created_at > cursor_created_at,
                            and_(
                                Product.created_at == cursor_created_at,
                                Product.id > after_id,
                            ),
                        )
                    )
            else:
                cursor_product = await self.get_product(
                    ProductSpec(
                        id=after_id,
                        include_inventory=True,
                        approved_only=True,
                    )
                )
                if cursor_product is None:
                    return [], False

                if sort == "popular":
                    cursor_quantity = cursor_product.inventory.quantity
                    stmt = stmt.where(
                        or_(
                            Inventory.quantity < cursor_quantity,
                            and_(
                                Inventory.quantity == cursor_quantity,
                                Product.id < after_id,
                            ),
                        )
                    )
                elif sort == "price-asc":
                    cursor_price = cursor_product.price
                    stmt = stmt.where(
                        or_(
                            Product.price > cursor_price,
                            and_(
                                Product.price == cursor_price,
                                Product.id > after_id,
                            ),
                        )
                    )
                elif sort == "price-desc":
                    cursor_price = cursor_product.price
                    stmt = stmt.where(
                        or_(
                            Product.price < cursor_price,
                            and_(
                                Product.price == cursor_price,
                                Product.id < after_id,
                            ),
                        )
                    )

        if sort == "popular":
            stmt = stmt.order_by(Inventory.quantity.desc(), Product.id.desc())
        elif sort == "price-asc":
            stmt = stmt.order_by(Product.price.asc(), Product.id.asc())
        elif sort == "price-desc":
            stmt = stmt.order_by(Product.price.desc(), Product.id.desc())
        elif sort == "newest":
            stmt = stmt.order_by(Product.created_at.desc(), Product.id.desc())
        elif sort == "oldest":
            stmt = stmt.order_by(Product.created_at.asc(), Product.id.asc())

        stmt = stmt.options(*self._product_list_options()).limit(limit + 1)
        result = await self.session.execute(stmt)
        products = list(result.scalars().all())

        has_more = len(products) > limit
        if has_more:
            products = products[:limit]

        return products, has_more

    async def get_facet_source_rows(
        self,
    ) -> list[tuple[str | None, str | None, str | None]]:
        stmt = select(
            Product.category_slug,
            Subcategory.slug,
            Product.fandom_slug,
        ).outerjoin(Subcategory, Product.subcategory_id == Subcategory.id)
        stmt = self._apply_approved_filter(stmt)
        result = await self.session.execute(stmt)
        return [
            (category_slug, subcategory_slug, fandom_slug)
            for category_slug, subcategory_slug, fandom_slug in result.all()
        ]

    def add(self, product: Product) -> Product:
        self.session.add(product)
        return product

    async def delete(self, product: Product) -> None:
        await self.session.delete(product)
