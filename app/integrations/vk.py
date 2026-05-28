import os
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status

VK_API_URL = "https://api.vk.com/method/users.get"
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class VkUserInfo:
    id: int
    first_name: str
    last_name: str
    screen_name: str | None


async def fetch_vk_user(access_token: str) -> VkUserInfo:
    params = {
        "access_token": access_token,
        "fields": "screen_name",
        "v": VK_API_VERSION,
    }

    try:
        async with httpx.AsyncClient(timeout=VK_HTTP_TIMEOUT) as client:
            response = await client.get(VK_API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK API request failed",
        ) from error

    if "error" in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid VK access token",
        )

    users = payload.get("response")
    if not users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK user not found",
        )

    user = users[0]
    return VkUserInfo(
        id=int(user["id"]),
        first_name=user.get("first_name", ""),
        last_name=user.get("last_name", ""),
        screen_name=user.get("screen_name") or None,
    )
