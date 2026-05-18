from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import database

DatabaseDepends = Annotated[
    AsyncSession,
    Depends(database.get_db),
]
