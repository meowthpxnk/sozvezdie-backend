from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.product import ProductRepository

CACHE_PREFIX = "catalog:facets"
KEY_TOTAL = f"{CACHE_PREFIX}:total"
KEY_BY_CATEGORY = f"{CACHE_PREFIX}:by_category"
KEY_BY_FANDOM = f"{CACHE_PREFIX}:by_fandom"


@dataclass(frozen=True)
class ProductFacetAttributes:
    category_slug: str | None = None
    subcategory_slug: str | None = None
    fandom_slug: str | None = None


class CatalogFacetCacheService:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def _category_total_key(category_slug: str) -> str:
        return f"{CACHE_PREFIX}:category:{category_slug}:total"

    @staticmethod
    def _subcategory_hash_key(category_slug: str) -> str:
        return f"{CACHE_PREFIX}:subcategory:{category_slug}"

    @staticmethod
    def _fandom_total_key(fandom_slug: str) -> str:
        return f"{CACHE_PREFIX}:fandom:{fandom_slug}:total"

    @staticmethod
    def _fandom_by_category_key(fandom_slug: str) -> str:
        return f"{CACHE_PREFIX}:fandom:{fandom_slug}:by_category"

    @staticmethod
    def _category_fandom_total_key(category_slug: str, fandom_slug: str) -> str:
        return (
            f"{CACHE_PREFIX}:category:{category_slug}:fandom:{fandom_slug}:total"
        )

    @staticmethod
    def _category_fandom_subcategory_key(
        category_slug: str, fandom_slug: str
    ) -> str:
        return (
            f"{CACHE_PREFIX}:category:{category_slug}:fandom:{fandom_slug}:"
            f"by_subcategory"
        )

    @staticmethod
    def _category_by_fandom_key(category_slug: str) -> str:
        return f"{CACHE_PREFIX}:category:{category_slug}:by_fandom"

    @staticmethod
    def _category_subcategory_total_key(
        category_slug: str, subcategory_slug: str
    ) -> str:
        return (
            f"{CACHE_PREFIX}:category:{category_slug}:subcategory:"
            f"{subcategory_slug}:total"
        )

    @staticmethod
    def _category_subcategory_by_fandom_key(
        category_slug: str, subcategory_slug: str
    ) -> str:
        return (
            f"{CACHE_PREFIX}:category:{category_slug}:subcategory:"
            f"{subcategory_slug}:by_fandom"
        )

    async def is_initialized(self) -> bool:
        return bool(await self.redis.exists(KEY_TOTAL))

    async def ensure_initialized(self, session: AsyncSession) -> None:
        if not await self.is_initialized():
            await self.rebuild(session)

    async def clear(self) -> None:
        keys: list[str] = []
        async for key in self.redis.scan_iter(match=f"{CACHE_PREFIX}:*"):
            keys.append(key)
        if keys:
            await self.redis.delete(*keys)

    async def rebuild(self, session: AsyncSession) -> None:
        await self.clear()
        rows = await ProductRepository(session).get_facet_source_rows()
        if not rows:
            await self.redis.set(KEY_TOTAL, 0)
            return

        pipe = self.redis.pipeline()
        for category_slug, subcategory_slug, fandom_slug in rows:
            self._queue_delta(
                pipe,
                ProductFacetAttributes(
                    category_slug=category_slug,
                    subcategory_slug=subcategory_slug,
                    fandom_slug=fandom_slug,
                ),
                delta=1,
            )
        await pipe.execute()

    async def apply_delta(
        self, attributes: ProductFacetAttributes, delta: int = 1
    ) -> None:
        if delta == 0:
            return

        pipe = self.redis.pipeline()
        self._queue_delta(pipe, attributes, delta)
        await pipe.execute()

    def _queue_delta(
        self,
        pipe,
        attributes: ProductFacetAttributes,
        delta: int,
    ) -> None:
        category_slug = attributes.category_slug
        subcategory_slug = attributes.subcategory_slug
        fandom_slug = attributes.fandom_slug

        pipe.incrby(KEY_TOTAL, delta)

        if category_slug:
            pipe.hincrby(KEY_BY_CATEGORY, category_slug, delta)
            pipe.incrby(self._category_total_key(category_slug), delta)

            if subcategory_slug:
                pipe.hincrby(
                    self._subcategory_hash_key(category_slug),
                    subcategory_slug,
                    delta,
                )

            if fandom_slug:
                pipe.hincrby(KEY_BY_FANDOM, fandom_slug, delta)
                pipe.incrby(self._fandom_total_key(fandom_slug), delta)
                pipe.hincrby(
                    self._fandom_by_category_key(fandom_slug),
                    category_slug,
                    delta,
                )
                pipe.incrby(
                    self._category_fandom_total_key(category_slug, fandom_slug),
                    delta,
                )
                pipe.hincrby(
                    self._category_fandom_subcategory_key(
                        category_slug, fandom_slug
                    ),
                    subcategory_slug or "__none__",
                    delta,
                )
                pipe.hincrby(
                    self._category_by_fandom_key(category_slug),
                    fandom_slug,
                    delta,
                )

                if subcategory_slug:
                    pipe.incrby(
                        self._category_subcategory_total_key(
                            category_slug, subcategory_slug
                        ),
                        delta,
                    )
                    pipe.hincrby(
                        self._category_subcategory_by_fandom_key(
                            category_slug, subcategory_slug
                        ),
                        fandom_slug,
                        delta,
                    )
        elif fandom_slug:
            pipe.hincrby(KEY_BY_FANDOM, fandom_slug, delta)
            pipe.incrby(self._fandom_total_key(fandom_slug), delta)

    async def replace_attributes(
        self,
        previous: ProductFacetAttributes,
        current: ProductFacetAttributes,
    ) -> None:
        if previous == current:
            return

        pipe = self.redis.pipeline()
        self._queue_delta(pipe, previous, delta=-1)
        self._queue_delta(pipe, current, delta=1)
        await pipe.execute()

    @staticmethod
    def _parse_hash_items(
        items: dict[bytes | str, bytes | str] | dict[str, int],
    ) -> list[tuple[str, int]]:
        parsed: list[tuple[str, int]] = []
        for slug, count in items.items():
            slug_str = slug.decode() if isinstance(slug, bytes) else slug
            if slug_str == "__none__":
                continue
            count_value = count.decode() if isinstance(count, bytes) else count
            parsed.append((slug_str, int(count_value)))
        return parsed

    async def get_category_facets(
        self, fandom_slug: str | None
    ) -> tuple[int, dict[str, int]]:
        if fandom_slug:
            total_raw = await self.redis.get(self._fandom_total_key(fandom_slug))
            items_raw = await self.redis.hgetall(
                self._fandom_by_category_key(fandom_slug)
            )
        else:
            total_raw = await self.redis.get(KEY_TOTAL)
            items_raw = await self.redis.hgetall(KEY_BY_CATEGORY)

        total = int(total_raw or 0)
        items = dict(self._parse_hash_items(items_raw or {}))
        return total, items

    async def get_subcategory_facets(
        self, category_slug: str, fandom_slug: str | None
    ) -> tuple[int, dict[str, int]]:
        if fandom_slug:
            total_raw = await self.redis.get(
                self._category_fandom_total_key(category_slug, fandom_slug)
            )
            items_raw = await self.redis.hgetall(
                self._category_fandom_subcategory_key(category_slug, fandom_slug)
            )
        else:
            total_raw = await self.redis.get(
                self._category_total_key(category_slug)
            )
            items_raw = await self.redis.hgetall(
                self._subcategory_hash_key(category_slug)
            )

        total = int(total_raw or 0)
        items = dict(self._parse_hash_items(items_raw or {}))
        if "__none__" in items:
            items.pop("__none__", None)
        return total, items

    async def get_fandom_facets(
        self,
        category_slug: str | None,
        subcategory_slug: str | None,
    ) -> tuple[int, dict[str, int]]:
        if category_slug and subcategory_slug:
            total_raw = await self.redis.get(
                self._category_subcategory_total_key(
                    category_slug, subcategory_slug
                )
            )
            items_raw = await self.redis.hgetall(
                self._category_subcategory_by_fandom_key(
                    category_slug, subcategory_slug
                )
            )
        elif category_slug:
            total_raw = await self.redis.get(
                self._category_total_key(category_slug)
            )
            items_raw = await self.redis.hgetall(
                self._category_by_fandom_key(category_slug)
            )
        else:
            total_raw = await self.redis.get(KEY_TOTAL)
            items_raw = await self.redis.hgetall(KEY_BY_FANDOM)

        total = int(total_raw or 0)
        items = dict(self._parse_hash_items(items_raw or {}))
        return total, items
