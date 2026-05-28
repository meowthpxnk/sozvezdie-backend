import logging
import os
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("app")

VK_API_URL = "https://api.vk.com/method/users.get"
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class VkUserInfo:
    id: int
    first_name: str
    last_name: str
    screen_name: str | None


def _mask_token(token: str) -> str:
    if not token:
        return "<empty>"
    if len(token) <= 8:
        return f"<len={len(token)}>"
    return f"<len={len(token)}, …{token[-4:]}>"


async def fetch_vk_user(access_token: str) -> VkUserInfo:
    params = {
        "access_token": access_token,
        "fields": "screen_name",
        "v": VK_API_VERSION,
    }

    logger.info(
        "VK users.get request (token=%s, v=%s)",
        _mask_token(access_token),
        VK_API_VERSION,
    )

    try:
        async with httpx.AsyncClient(timeout=VK_HTTP_TIMEOUT) as client:
            response = await client.get(VK_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        logger.warning(
            "VK users.get HTTP error (token=%s): %s",
            _mask_token(access_token),
            error,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK API request failed",
        ) from error

    if "error" in payload:
        vk_error = payload["error"]
        logger.warning(
            "VK users.get API error (token=%s): %s",
            _mask_token(access_token),
            vk_error,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid VK access token",
        )

    users = payload.get("response")
    if not users:
        logger.warning(
            "VK users.get empty response (token=%s), payload keys=%s",
            _mask_token(access_token),
            list(payload.keys()),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK user not found",
        )

    user = users[0]
    vk_user = VkUserInfo(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        screen_name=user.get("screen_name") or None,
    )
    logger.info(
        "VK users.get ok: vk_id=%s screen_name=%s",
        vk_user.id,
        vk_user.screen_name,
    )
    return vk_user
