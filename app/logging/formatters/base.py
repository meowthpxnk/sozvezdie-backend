import logging
import os
import time
from dataclasses import dataclass


@dataclass
class FormatterSettings:
    datetime: bool = True
    module: bool = False
    log_path: bool = False


BASE_FORMATTER_SETTINGS = FormatterSettings()

_levelToName = {
    logging.CRITICAL: "FATAL",
    logging.ERROR: "ERROR",
    logging.WARNING: "WARN",
    logging.INFO: "INFO",
    logging.DEBUG: "DEBUG",
    logging.NOTSET: "NOTSET",
}


class BaseFormatter(logging.Formatter):
    LEVELNO_MAP = _levelToName

    def __init__(
        self, settings: FormatterSettings | dict = BASE_FORMATTER_SETTINGS
    ):
        if not isinstance(settings, FormatterSettings | dict):
            raise ValueError(
                "Formatter settings must be dict or FormatterSettings"
            )

        if isinstance(settings, dict):
            settings = FormatterSettings(**settings)

        self.settings = settings

    def format(self, record: logging.LogRecord) -> str:
        data = []
        message = record.getMessage()

        if self.settings.datetime:
            data.append(f"[{self._datetime_str(record.created)}]")

        data.append(f"{self._level_to_name(record.levelno)}")

        if self.settings.module:
            data.append(f"[{record.name}]")

        if self.settings.log_path:
            log_path = self._log_path_str(record.pathname, record.lineno)
            data.append(log_path)

        return " ".join(data) + f": {message}"

    @classmethod
    def _log_path_data_str(cls, data: str) -> str:
        return data

    @classmethod
    def _log_path_str(cls, pathname: str, line: str) -> str:
        filename = cls._pathname_str(pathname)
        line = cls._line_str(line)
        return f"in {filename} line {line}"

    @classmethod
    def _pathname_str(cls, pathname: str) -> str:
        pathname = pathname.replace(os.path.abspath(""), ".")
        return cls._log_path_data_str(pathname)

    @classmethod
    def _line_str(cls, line: str) -> str:
        return cls._log_path_data_str(str(line))

    @classmethod
    def _level_to_name(cls, levelno: int) -> str:
        try:
            levelname = cls.LEVELNO_MAP[levelno]
        except KeyError:
            levelname = f"UNKNOWN LEVELNO - {levelno}"
        return f"{levelname}"

    @classmethod
    def _datetime_str(self, created: float) -> str:
        return time.strftime(self.default_time_format, self.converter(created))
