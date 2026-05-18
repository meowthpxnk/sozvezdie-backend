from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.constants import DOCS_HTML_PATH
from app.utils.files import read_file

router = APIRouter()


@router.get("/docs", include_in_schema=False)
def documentation() -> HTMLResponse:
    print("documentation")
    print("documentation")
    print("documentation")
    return HTMLResponse(read_file(DOCS_HTML_PATH))
