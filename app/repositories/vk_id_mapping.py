from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import VkIdMapping


class VkIdMappingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_vk_id(self, vk_id: int) -> VkIdMapping | None:
        stmt = select(VkIdMapping).where(VkIdMapping.vk_id == vk_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def add(self, mapping: VkIdMapping) -> VkIdMapping:
        self.session.add(mapping)
        return mapping
