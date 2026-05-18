from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.constants import FAVICON_PATH

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    return FileResponse(FAVICON_PATH)
