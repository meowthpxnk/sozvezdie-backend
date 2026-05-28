import logging
import os
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("app")

VK_API_URL = "https://api.vk.com/method/users.get"
VK_API_VERSION = os.getenv("VK_API_VERSION", "5.199")
VK_HTTP_TIMEOUT = 10.0
VK_OAUTH_DOMAIN = os.getenv("VK_OAUTH_DOMAIN", "id.vk.ru")
VK_CLIENT_ID = os.getenv("VK_CLIENT_ID", "")
VK_REDIRECT_URI = os.getenv("VK_REDIRECT_URI", "")


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
    return f"<len={len(token)}, …{token[-4:]}"


def _mask_code(code: str) -> str:
    if not code:
        return "<empty>"
    if len(code) <= 12:
        return f"<len={len(code)}>"
    return f"<len={len(code)}, …{code[-6:]}"


async def exchange_code_for_access_token(
    code: str,
    device_id: str,
    code_verifier: str,
) -> str:
    if not VK_CLIENT_ID or not VK_REDIRECT_URI:
        logger.error(
            "VK OAuth not configured: VK_CLIENT_ID=%s VK_REDIRECT_URI=%s",
            bool(VK_CLIENT_ID),
            bool(VK_REDIRECT_URI),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VK OAuth is not configured on server",
        )

    query_params = urlencode(
        {
            "grant_type": "authorization_code",
            "redirect_uri": VK_REDIRECT_URI,
            "device_id": device_id,
            "client_id": VK_CLIENT_ID,
            "code_verifier": code_verifier,
        }
    )
    url = f"https://{VK_OAUTH_DOMAIN}/oauth2/auth?{query_params}"

    logger.info(
        "VK oauth2/auth exchange (code=%s device_id_len=%s verifier_len=%s client_id=%s)",
        _mask_code(code),
        len(device_id),
        len(code_verifier),
        VK_CLIENT_ID,
    )

    try:
        async with httpx.AsyncClient(timeout=VK_HTTP_TIMEOUT) as client:
            response = await client.post(
                url,
                json={"code": code},
                headers={
                    "Accept": "*/*",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as error:
        logger.warning(
            "VK oauth2/auth HTTP error (code=%s): %s",
            _mask_code(code),
            error,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK token exchange failed",
        ) from error

    if "error" in payload:
        logger.warning(
            "VK oauth2/auth API error (code=%s): %s",
            _mask_code(code),
            payload.get("error"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK authorization code exchange failed",
        )

    access_token = payload.get("access_token")
    if not access_token or not str(access_token).strip():
        logger.warning(
            "VK oauth2/auth missing access_token (code=%s), keys=%s",
            _mask_code(code),
            list(payload.keys()),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="VK did not return access token",
        )

    logger.info(
        "VK oauth2/auth ok (code=%s, user_id=%s)",
        _mask_code(code),
        payload.get("user_id"),
    )
    return str(access_token).strip()


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
