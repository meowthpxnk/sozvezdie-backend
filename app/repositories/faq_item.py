from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FaqItem


class FaqItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    def add(self, item: FaqItem) -> FaqItem:
        self.session.add(item)
        return item

    async def delete(self, item: FaqItem) -> None:
        await self.session.delete(item)

    async def get_by_id(self, item_id: int) -> FaqItem | None:
        stmt = select(FaqItem).where(FaqItem.id == item_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_next_sort_order(self) -> int:
        stmt = select(func.coalesce(func.max(FaqItem.sort_order), -1))
        result = await self.session.execute(stmt)
        return int(result.scalar_one()) + 1

    async def list_items(self, *, search: str | None = None) -> list[FaqItem]:
        stmt = select(FaqItem).order_by(FaqItem.sort_order.asc(), FaqItem.id.asc())
        if search:
            pattern = f"%{search.strip()}%"
            stmt = stmt.where(
                or_(
                    FaqItem.question.ilike(pattern),
                    FaqItem.answer.ilike(pattern),
                )
            )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
