import logging
import os
from dotenv import load_dotenv
import uvicorn

from app.core.logging import LOGGING_CONFIG

logger = logging.getLogger("app")


def startup():
    logger.info("Startup application")
    load_dotenv()
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "app.core.api:api.api",  # 🔥 строка обязательна
        host="0.0.0.0",
        port=port,
        log_config=LOGGING_CONFIG,
        reload=True,
    )
