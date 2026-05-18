import traceback

from pydantic_core import ErrorDetails
from starlette.types import Scope
from uvicorn.protocols.utils import get_client_addr, get_path_with_query_string


def prepare_request_exception(scope: Scope, error: Exception) -> str:
    addr = get_client_addr(scope)
    path = get_path_with_query_string(scope)
    method = scope["method"]
    version = scope["http_version"]
    return (
        f"{addr} - '{method} {path} {version}', reason: {error}\n"
        f"Traceback: {traceback.format_exc()}"
    )


def prepare_settings_errors_message(errors: list[ErrorDetails]) -> str:
    def prepare_single(error: ErrorDetails) -> str:
        messages = []
        messages.append(
            f"- {'.'.join(map(str, error['loc']))}:",
        )
        if error["type"] != "missing":
            messages.append(
                f"Input - {error['input']}",
            )
        messages.append(
            f"Error - {error['msg']}",
        )
        return " | ".join(messages)

    return "Settings initialisation error:\n" + "\n".join(
        [prepare_single(e) for e in errors]
    )
