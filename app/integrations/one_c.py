import asyncio

ONE_C_TIMEOUT_SECONDS = 5.0
ONE_C_CREATE_ERROR = "Нет доступа к 1C введите код вручную"
ONE_C_DELETE_ERROR = "Нет доступа к 1C удалите автора вручную."


class OneCUnavailable(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


async def create_author() -> str:
    await asyncio.sleep(ONE_C_TIMEOUT_SECONDS)
    raise OneCUnavailable(ONE_C_CREATE_ERROR)


async def delete_author(_one_c_author_id: str) -> None:
    await asyncio.sleep(ONE_C_TIMEOUT_SECONDS)
    raise OneCUnavailable(ONE_C_DELETE_ERROR)
