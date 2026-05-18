import random

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.models import Product, ProductImage, Inventory, ProductModeration
from app.repositories.fandom import FandomRepository
from app.repositories.subcategory import SubcategoryRepository
from app.schemas.api.responses import (
    ProductFacetCountItem,
    ProductFacetsResponse,
    ProductResponse,
    ProductsPageResponse,
    SellerProductResponse,
)
from app.repositories.seller_card import SellerCardRepository
from app.services.catalog_facet_cache import (
    CatalogFacetCacheService,
    ProductFacetAttributes,
)
from app.schemas.schemas import (
    ProductCreateForm,
    ProductUpdateForm,
)
from app.media_client import MediaClient

from app.repositories.product import ProductRepository

from app.repositories.specs.product import ProductSpec
from app.schemas.database import ModerationStatus


class ProductService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProductRepository(session)
        self.subcategory_repo = SubcategoryRepository(session)
        self.fandom_repo = FandomRepository(session)
        self.facet_cache = CatalogFacetCacheService(redis_client)

    @staticmethod
    def _facets_response(
        total: int, counts: dict[str, int]
    ) -> ProductFacetsResponse:
        return ProductFacetsResponse(
            total=total,
            items=[
                ProductFacetCountItem(slug=slug, count=count)
                for slug, count in sorted(
                    counts.items(), key=lambda item: item[0]
                )
            ],
        )

    @staticmethod
    def _to_response(product: Product) -> ProductResponse:
        return ProductResponse(
            id=str(product.id),
            name=product.name,
            description=product.desc,
            price=product.price,
            stockCount=product.inventory.quantity,
            images=[str(image.image_uuid) for image in product.images],
            authorId=str(product.seller_card.id),
            categorySlug=product.category_slug,
            subcategorySlug=(
                product.subcategory.slug if product.subcategory else None
            ),
            fandomSlug=product.fandom_slug,
        )

    async def create_product(
        self,
        data: ProductCreateForm,
        media_client: MediaClient,
    ) -> Product:
        subcategory_id = None
        category_slug = data.category_slug

        if data.subcategory_slug and category_slug:
            subcategory = await self.subcategory_repo.get_by_slugs(
                category_slug, data.subcategory_slug
            )
            if subcategory is None:
                raise ValueError("Subcategory not found")
            if subcategory.seller_card_id != data.seller_card_id:
                raise ValueError("Subcategory does not belong to seller")
            subcategory_id = subcategory.id
        elif category_slug:
            pass
        else:
            category_slug = None

        fandom_slug = data.fandom_slug
        if fandom_slug:
            fandom = await self.fandom_repo.get_by_slug(fandom_slug)
            if fandom is None:
                raise ValueError("Fandom not found")
        else:
            fandom_slug = None

        product = Product(
            name=data.name,
            desc=data.desc,
            price=data.price,
            seller_card_id=data.seller_card_id,
            status=data.status,
            category_slug=category_slug,
            subcategory_id=subcategory_id,
            fandom_slug=fandom_slug,
        )

        for index, file in enumerate(data.images):
            content = await file.read()

            content_type = file.content_type or "image/jpeg"
            image_id = await media_client.upload_image(
                image_bytes=content,
                content_type=content_type,
            )

            image = ProductImage(
                image_uuid=image_id,
                order=index,
            )

            product.images.append(image)

        inventory = Inventory(
            product_id=product.id,
            quantity=data.quantity,
        )

        product.inventory = inventory

        self.repo.add(product)
        await self.session.commit()

        subcategory_slug_for_cache = None
        if subcategory_id is not None and data.subcategory_slug:
            subcategory_slug_for_cache = data.subcategory_slug

        await self.facet_cache.apply_delta(
            ProductFacetAttributes(
                category_slug=category_slug,
                subcategory_slug=subcategory_slug_for_cache,
                fandom_slug=fandom_slug,
            )
        )

        return product

    async def get_seller_product_by_id(
        self, user_id: int, product_id: int
    ) -> SellerProductResponse:
        seller_card = await SellerCardRepository(self.session).get_by_user_id(
            user_id
        )
        if seller_card is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Seller card not found")

        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(seller_card.id),
                approved_only=False,
                include_moderations=True,
            )
        )
        if product is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Product not found")

        return self._to_seller_response(product)

    async def get_product_for_moderation(self, product_id: int) -> SellerProductResponse:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_subcategory=True,
                include_moderations=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.PENDING:
            raise ValueError("Product is not pending moderation")

        return self._to_seller_response(product)

    async def get_product_for_moderator_catalog_edit(
        self, product_id: int
    ) -> SellerProductResponse:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_subcategory=True,
                include_moderations=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.APPROVED:
            raise ValueError("Only approved products can be edited by a moderator")

        return self._to_seller_response(product)

    async def update_product_for_moderation(
        self,
        product_id: int,
        data: ProductUpdateForm,
        media_client: MediaClient,
    ) -> Product:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_subcategory=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.PENDING:
            raise ValueError("Product is not pending moderation")
        if product.seller_card_id is None:
            raise ValueError("Product seller not found")

        data.seller_card_id = product.seller_card_id
        return await self.update_product_for_seller(product_id, data, media_client)

    async def update_product_for_seller(
        self,
        product_id: int,
        data: ProductUpdateForm,
        media_client: MediaClient,
    ) -> Product:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(data.seller_card_id),
                include_images=True,
                include_inventory=True,
                include_subcategory=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")

        await self._apply_product_update(product, data, media_client)
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def update_product_by_moderator(
        self,
        product_id: int,
        data: ProductUpdateForm,
        media_client: MediaClient,
        moderator_id: int,
        comment: str | None,
    ) -> Product:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                include_images=True,
                include_inventory=True,
                include_subcategory=True,
                approved_only=False,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.APPROVED:
            raise ValueError("Only approved products can be edited by a moderator")
        if product.seller_card_id is None:
            raise ValueError("Product seller not found")

        data.seller_card_id = product.seller_card_id
        await self._apply_product_update(
            product,
            data,
            media_client,
            preserve_moderation_status=True,
        )

        moderation_comment = (comment or "Изменение применено модератором.").strip()
        if not moderation_comment:
            raise ValueError("Comment is required")

        self.session.add(
            ProductModeration(
                product_id=product.id,
                moderator_id=moderator_id,
                status=ModerationStatus.APPROVED,
                comment=moderation_comment,
            )
        )
        await self.session.commit()
        await self.session.refresh(product)
        return product

    async def _apply_product_update(
        self,
        product: Product,
        data: ProductUpdateForm,
        media_client: MediaClient,
        *,
        preserve_moderation_status: bool = False,
    ) -> None:
        subcategory_id = None
        category_slug = data.category_slug

        if data.subcategory_slug and category_slug:
            subcategory = await self.subcategory_repo.get_by_slugs(
                category_slug, data.subcategory_slug
            )
            if subcategory is None:
                raise ValueError("Subcategory not found")
            if subcategory.seller_card_id != data.seller_card_id:
                raise ValueError("Subcategory does not belong to seller")
            subcategory_id = subcategory.id
        elif not category_slug:
            category_slug = None

        fandom_slug = data.fandom_slug
        if fandom_slug:
            fandom = await self.fandom_repo.get_by_slug(fandom_slug)
            if fandom is None:
                raise ValueError("Fandom not found")
        else:
            fandom_slug = None

        product.name = data.name
        product.desc = data.desc
        product.price = data.price
        if not preserve_moderation_status:
            product.status = ModerationStatus.PENDING
        product.category_slug = category_slug
        product.subcategory_id = subcategory_id
        product.fandom_slug = fandom_slug

        if product.inventory is None:
            product.inventory = Inventory(product_id=product.id, quantity=data.quantity)
        else:
            product.inventory.quantity = data.quantity

        product.images.clear()
        new_file_index = 0
        for order, slot in enumerate(data.image_slots):
            if slot.type == "existing":
                if not slot.uuid:
                    raise ValueError("Existing image uuid is required")
                product.images.append(
                    ProductImage(
                        image_uuid=slot.uuid,
                        order=order,
                    )
                )
                continue

            if slot.type != "new":
                raise ValueError("Invalid image slot type")

            if new_file_index >= len(data.new_images):
                raise ValueError("Not enough image files provided")

            file = data.new_images[new_file_index]
            new_file_index += 1
            content = await file.read()
            content_type = file.content_type or "image/jpeg"
            image_id = await media_client.upload_image(
                image_bytes=content,
                content_type=content_type,
            )
            product.images.append(
                ProductImage(
                    image_uuid=image_id,
                    order=order,
                )
            )

        if new_file_index != len(data.new_images):
            raise ValueError("Too many image files provided")

        if not product.images:
            raise ValueError("Product must have at least one image")

    async def get_products_page(
        self,
        *,
        category_slug: str | None = None,
        subcategory_slug: str | None = None,
        fandom_slug: str | None = None,
        limit: int = 20,
        after_id: int | None = None,
        sort: str = "popular",
        starts_with: str | None = None,
    ) -> ProductsPageResponse:
        products, has_more = await self.repo.get_page(
            category_slug=category_slug,
            subcategory_slug=subcategory_slug,
            fandom_slug=fandom_slug,
            limit=limit,
            after_id=after_id,
            sort=sort,
            starts_with=starts_with,
        )
        items = [self._to_response(product) for product in products]
        next_cursor_id = items[-1].id if has_more and items else None

        return ProductsPageResponse(
            items=items,
            nextCursorId=next_cursor_id,
            hasMore=has_more,
        )

    async def get_product(self, product_id: int) -> ProductResponse:
        product = await self.repo.get_product(
            ProductSpec(id=product_id, approved_only=True)
        )
        if product is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Product not found")
        return self._to_response(product)

    async def get_similar_products(
        self, product_id: int, *, limit: int = 20
    ) -> list[ProductResponse]:
        from fastapi import HTTPException

        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                approved_only=True,
                include_subcategory=True,
            )
        )
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")

        limit = max(1, min(limit, 50))
        pool = await self.repo.get_similar_pool(
            product_id=product_id,
            fandom_slug=product.fandom_slug,
            subcategory_id=product.subcategory_id,
            category_slug=product.category_slug,
            pool_limit=100,
        )
        if not pool:
            return []

        if len(pool) > limit:
            selected = random.sample(pool, limit)
        else:
            selected = list(pool)
            random.shuffle(selected)

        return [self._to_response(item) for item in selected]

    async def get_products_by_ids(
        self, product_ids: list[str]
    ) -> list[ProductResponse]:
        if not product_ids:
            return []

        ids = [int(product_id) for product_id in product_ids]
        products = await self.repo.get_product(
            ProductSpec(ids=ids, all=True, approved_only=False)
        )
        products_by_id = {product.id: product for product in products}

        return [
            self._to_response(products_by_id[product_id])
            for product_id in ids
            if product_id in products_by_id
        ]

    @staticmethod
    def _latest_moderator_comment(product: Product) -> str | None:
        if product.status != ModerationStatus.REJECTED or not product.moderations:
            return None

        latest = max(product.moderations, key=lambda moderation: moderation.created_at)
        comment = latest.comment.strip()
        return comment or None

    def _to_seller_response(self, product: Product) -> SellerProductResponse:
        response = self._to_response(product)
        return SellerProductResponse(
            **response.model_dump(),
            moderationStatus=product.status,
            createdAt=product.created_at,
            moderatorComment=self._latest_moderator_comment(product),
        )

    async def get_products_for_seller_user(
        self, user_id: int
    ) -> list[SellerProductResponse]:
        seller_card = await SellerCardRepository(self.session).get_by_user_id(
            user_id
        )
        if seller_card is None:
            return []

        products = await self.repo.get_product(
            ProductSpec(
                seller_card_id=str(seller_card.id),
                all=True,
                approved_only=False,
                include_moderations=True,
            )
        )
        products = sorted(products, key=lambda product: product.created_at, reverse=True)
        return [self._to_seller_response(product) for product in products]

    async def get_products_by_author_id(
        self, author_id: str
    ) -> list[ProductResponse]:
        products = await self.repo.get_product(
            ProductSpec(
                seller_card_id=author_id,
                all=True,
                approved_only=True,
            )
        )
        return [self._to_response(product) for product in products]

    async def get_category_facets(
        self, fandom_slug: str | None = None
    ) -> ProductFacetsResponse:
        await self.facet_cache.ensure_initialized(self.session)
        total, counts = await self.facet_cache.get_category_facets(fandom_slug)
        return self._facets_response(total, counts)

    async def get_subcategory_facets(
        self,
        category_slug: str,
        fandom_slug: str | None = None,
    ) -> ProductFacetsResponse:
        await self.facet_cache.ensure_initialized(self.session)
        total, counts = await self.facet_cache.get_subcategory_facets(
            category_slug, fandom_slug
        )
        return self._facets_response(total, counts)

    async def get_fandom_facets(
        self,
        category_slug: str | None = None,
        subcategory_slug: str | None = None,
    ) -> ProductFacetsResponse:
        await self.facet_cache.ensure_initialized(self.session)
        total, counts = await self.facet_cache.get_fandom_facets(
            category_slug, subcategory_slug
        )
        return self._facets_response(total, counts)
