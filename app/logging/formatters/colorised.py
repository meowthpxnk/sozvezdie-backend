import logging

import colorama

from . import BaseFormatter

_levelToName_COLORISED = {
    logging.INFO: f"{colorama.Fore.GREEN}INFO{colorama.Fore.RESET}",
    logging.ERROR: f"{colorama.Fore.RED}ERROR{colorama.Fore.RESET}",
    logging.WARN: f"{colorama.Fore.YELLOW}WARN{colorama.Fore.RESET}",
    logging.DEBUG: f"{colorama.Fore.LIGHTBLACK_EX}DEBUG{colorama.Fore.RESET}",
    logging.FATAL: f"{colorama.Back.RED}FATAL{colorama.Back.RESET}",
}


class ColorisedFormatter(BaseFormatter):
    LEVELNO_MAP = _levelToName_COLORISED

    @classmethod
    def _level_to_name(cls, levelno: int) -> str:
        levelname = super()._level_to_name(levelno)
        return f"{levelname}"

    @classmethod
    def _datetime_str(cls, created: float) -> str:
        dt = super()._datetime_str(created)
        return f"{colorama.Style.DIM}{dt}{colorama.Style.NORMAL}"

    @classmethod
    def _log_path_data_str(cls, data: str) -> str:
        data = super()._log_path_data_str(data)
        return f"{colorama.Fore.LIGHTYELLOW_EX}{data}{colorama.Fore.RESET}"
