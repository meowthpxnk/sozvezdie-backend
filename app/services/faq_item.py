from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FaqItem
from app.repositories.faq_item import FaqItemRepository
from app.schemas.api.responses import FaqItemResponse
from app.schemas.schemas import (
    FaqItemCreateRequest,
    FaqItemReorderRequest,
    FaqItemUpdateRequest,
)


class FaqItemService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = FaqItemRepository(session)

    def _to_response(self, item: FaqItem) -> FaqItemResponse:
        return FaqItemResponse(
            id=item.id,
            question=item.question,
            answer=item.answer,
            sortOrder=item.sort_order,
        )

    async def list_items(self, *, search: str | None = None) -> list[FaqItemResponse]:
        items = await self.repo.list_items(search=search)
        return [self._to_response(item) for item in items]

    async def create_item(self, data: FaqItemCreateRequest) -> FaqItemResponse:
        item = FaqItem(
            question=data.question.strip(),
            answer=data.answer.strip(),
            sort_order=await self.repo.get_next_sort_order(),
        )
        self.repo.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return self._to_response(item)

    async def update_item(
        self, item_id: int, data: FaqItemUpdateRequest
    ) -> FaqItemResponse:
        item = await self.repo.get_by_id(item_id)
        if item is None:
            raise ValueError("FAQ item not found")

        item.question = data.question.strip()
        item.answer = data.answer.strip()
        await self.session.commit()
        await self.session.refresh(item)
        return self._to_response(item)

    async def delete_item(self, item_id: int) -> None:
        item = await self.repo.get_by_id(item_id)
        if item is None:
            raise ValueError("FAQ item not found")
        await self.repo.delete(item)
        await self.session.commit()

    async def reorder_items(self, data: FaqItemReorderRequest) -> list[FaqItemResponse]:
        items = await self.repo.list_items()
        items_by_id = {item.id: item for item in items}
        ordered_ids = data.ordered_ids

        if len(ordered_ids) != len(items_by_id):
            raise ValueError("Ordered ids must include all FAQ items")

        if len(set(ordered_ids)) != len(ordered_ids):
            raise ValueError("Ordered ids must be unique")

        if any(item_id not in items_by_id for item_id in ordered_ids):
            raise ValueError("Unknown FAQ item id in ordered ids")

        for index, item_id in enumerate(ordered_ids):
            items_by_id[item_id].sort_order = index

        await self.session.commit()
        return await self.list_items()
