import logging
import logging.config

from app.core import settings
from app.utils.files import read_yaml

LOGGING_CONFIG = read_yaml(settings.logging.config_path)
logging.config.dictConfig(LOGGING_CONFIG)
