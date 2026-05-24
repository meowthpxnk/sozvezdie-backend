import logging
from dotenv import load_dotenv
import uvicorn

from app.core.logging import LOGGING_CONFIG

logger = logging.getLogger("app")


def startup():
    logger.info("Startup application")
    load_dotenv()

    uvicorn.run(
        "app.core.api:api.api",  # 🔥 строка обязательна
        host="0.0.0.0",
        port=8000,
        log_config=LOGGING_CONFIG,
        reload=True,
    )
