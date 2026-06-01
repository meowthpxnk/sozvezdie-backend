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
        positive_counts = {
            slug: count for slug, count in counts.items() if count > 0
        }
        return ProductFacetsResponse(
            total=max(total, 0),
            items=[
                ProductFacetCountItem(slug=slug, count=count)
                for slug, count in sorted(
                    positive_counts.items(), key=lambda item: item[0]
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

    @staticmethod
    def _product_facet_attributes(product: Product) -> ProductFacetAttributes:
        subcategory_slug = (
            product.subcategory.slug if product.subcategory else None
        )
        return ProductFacetAttributes(
            category_slug=product.category_slug,
            subcategory_slug=subcategory_slug,
            fandom_slug=product.fandom_slug,
        )

    @staticmethod
    def _is_catalog_visible(product: Product) -> bool:
        if product.status != ModerationStatus.APPROVED:
            return False
        if product.deletion_request_status == ModerationStatus.PENDING:
            return False
        if product.inventory is None or product.inventory.quantity <= 0:
            return False
        return True

    async def _apply_catalog_facet_change(
        self,
        previous: ProductFacetAttributes | None,
        current: ProductFacetAttributes | None,
    ) -> None:
        if previous and current:
            if previous != current:
                await self.facet_cache.replace_attributes(previous, current)
            return
        if previous:
            await self.facet_cache.apply_delta(previous, delta=-1)
        if current:
            await self.facet_cache.apply_delta(current, delta=1)

    async def _sync_catalog_facet_after_change(
        self,
        product: Product,
        *,
        previous_attributes: ProductFacetAttributes | None,
        was_visible: bool,
    ) -> None:
        is_visible = self._is_catalog_visible(product)
        current_attributes = (
            self._product_facet_attributes(product) if is_visible else None
        )
        previous = previous_attributes if was_visible else None
        await self._apply_catalog_facet_change(previous, current_attributes)

    async def _delete_product_record(self, product: Product) -> None:
        was_visible = self._is_catalog_visible(product)
        facet_attributes = (
            self._product_facet_attributes(product) if was_visible else None
        )
        await self.repo.delete(product)
        await self.session.commit()
        if facet_attributes is not None:
            await self.facet_cache.apply_delta(facet_attributes, delta=-1)

    async def cancel_pending_product(self, user_id: int, product_id: int) -> None:
        seller_card = await SellerCardRepository(self.session).get_by_user_id(
            user_id
        )
        if seller_card is None:
            raise ValueError("Seller card not found")

        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(seller_card.id),
                approved_only=False,
                include_subcategory=True,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.PENDING:
            raise ValueError("Only pending products can be cancelled")

        await self._delete_product_record(product)

    async def request_product_deletion(
        self, user_id: int, product_id: int, reason: str | None = None
    ) -> SellerProductResponse:
        seller_card = await SellerCardRepository(self.session).get_by_user_id(
            user_id
        )
        if seller_card is None:
            raise ValueError("Seller card not found")

        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(seller_card.id),
                approved_only=False,
                include_inventory=True,
                include_subcategory=True,
                include_moderations=True,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.APPROVED:
            raise ValueError("Only approved products can be deleted")
        if product.deletion_request_status == ModerationStatus.PENDING:
            raise ValueError("Deletion request is already pending moderation")
        if product.deletion_request_status == ModerationStatus.APPROVED:
            raise ValueError("Product is already deleted")

        from datetime import datetime

        normalized_reason = reason.strip() if reason else None
        if normalized_reason == "":
            normalized_reason = None

        was_visible = self._is_catalog_visible(product)
        previous_attributes = (
            self._product_facet_attributes(product) if was_visible else None
        )

        product.deletion_request_status = ModerationStatus.PENDING
        product.deletion_request_reason = normalized_reason
        product.deletion_requested_at = datetime.now()

        await self.session.commit()
        await self.session.refresh(product)
        await self._sync_catalog_facet_after_change(
            product,
            previous_attributes=previous_attributes,
            was_visible=was_visible,
        )
        return self._to_seller_response(product)

    async def cancel_product_deletion_request(
        self, user_id: int, product_id: int
    ) -> SellerProductResponse:
        seller_card = await SellerCardRepository(self.session).get_by_user_id(
            user_id
        )
        if seller_card is None:
            raise ValueError("Seller card not found")

        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(seller_card.id),
                approved_only=False,
                include_inventory=True,
                include_subcategory=True,
                include_moderations=True,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.deletion_request_status != ModerationStatus.PENDING:
            raise ValueError("Only pending deletion requests can be cancelled")

        was_visible = self._is_catalog_visible(product)

        product.deletion_request_status = None
        product.deletion_request_reason = None
        product.deletion_requested_at = None

        await self.session.commit()
        await self.session.refresh(product)
        await self._sync_catalog_facet_after_change(
            product,
            previous_attributes=None,
            was_visible=was_visible,
        )
        return self._to_seller_response(product)

    async def delete_approved_product(self, product_id: int) -> None:
        product = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                approved_only=False,
                include_subcategory=True,
            )
        )
        if product is None:
            raise ValueError("Product not found")
        if product.status != ModerationStatus.APPROVED:
            raise ValueError("Product is not approved")

        await self._delete_product_record(product)

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
        if product.deletion_request_status == ModerationStatus.PENDING:
            raise ValueError("Cannot edit product while deletion is pending moderation")

        was_visible = self._is_catalog_visible(product)
        previous_attributes = (
            self._product_facet_attributes(product) if was_visible else None
        )

        await self._apply_product_update(product, data, media_client)
        await self.session.commit()

        refreshed = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                seller_card_id=str(data.seller_card_id),
                include_inventory=True,
                include_subcategory=True,
                approved_only=False,
            )
        )
        if refreshed is None:
            raise ValueError("Product not found")

        await self._sync_catalog_facet_after_change(
            refreshed,
            previous_attributes=previous_attributes,
            was_visible=was_visible,
        )
        return refreshed

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

        was_visible = self._is_catalog_visible(product)
        previous_attributes = (
            self._product_facet_attributes(product) if was_visible else None
        )

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

        refreshed = await self.repo.get_product(
            ProductSpec(
                id=product_id,
                include_inventory=True,
                include_subcategory=True,
                approved_only=False,
            )
        )
        if refreshed is None:
            raise ValueError("Product not found")

        await self._sync_catalog_facet_after_change(
            refreshed,
            previous_attributes=previous_attributes,
            was_visible=was_visible,
        )
        return refreshed

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

    @staticmethod
    def _latest_deletion_rejection_comment(product: Product) -> str | None:
        if product.deletion_request_status != ModerationStatus.REJECTED:
            return None
        if not product.moderations:
            return None

        deletion_comments = [
            moderation.comment.strip()
            for moderation in product.moderations
            if moderation.comment
            and moderation.comment.startswith("Удаление товара:")
        ]
        if not deletion_comments:
            return None

        return deletion_comments[-1].removeprefix("Удаление товара:").strip() or None

    def _to_seller_response(self, product: Product) -> SellerProductResponse:
        response = self._to_response(product)
        moderator_comment = self._latest_moderator_comment(product)
        if moderator_comment is None:
            moderator_comment = self._latest_deletion_rejection_comment(product)

        return SellerProductResponse(
            **response.model_dump(),
            moderationStatus=product.status,
            createdAt=product.created_at,
            moderatorComment=moderator_comment,
            deletionRequestStatus=product.deletion_request_status,
            deletionRequestReason=product.deletion_request_reason,
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
        total = await self.repo.count_catalog_products(fandom_slug=fandom_slug)
        counts = await self.repo.count_catalog_by_category(fandom_slug)
        return self._facets_response(total, counts)

    async def get_subcategory_facets(
        self,
        category_slug: str,
        fandom_slug: str | None = None,
    ) -> ProductFacetsResponse:
        total = await self.repo.count_catalog_products(
            category_slug=category_slug,
            fandom_slug=fandom_slug,
        )
        counts = await self.repo.count_catalog_by_subcategory(
            category_slug, fandom_slug
        )
        return self._facets_response(total, counts)

    async def get_fandom_facets(
        self,
        category_slug: str | None = None,
        subcategory_slug: str | None = None,
    ) -> ProductFacetsResponse:
        total = await self.repo.count_catalog_products(
            category_slug=category_slug,
            subcategory_slug=subcategory_slug,
        )
        counts = await self.repo.count_catalog_by_fandom(
            category_slug=category_slug,
            subcategory_slug=subcategory_slug,
        )
        return self._facets_response(total, counts)
