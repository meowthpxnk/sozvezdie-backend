import html
import json
import logging
import os
import secrets
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import redis_client
from app.integrations import rusender
from app.models import User
from app.repositories.specs.user import UserSpec
from app.repositories.user import UserRepository
from app.utils import security

logger = logging.getLogger("app")

CODE_TTL_SECONDS = 600
SEND_COOLDOWN_SECONDS = 60
MAX_ATTEMPTS = 5
CODE_LENGTH = 6

VERIFY_KEY_PREFIX = "emailVerify."
VERIFY_COOLDOWN_PREFIX = "emailVerifyCooldown."
RESET_KEY_PREFIX = "passwordReset."
RESET_COOLDOWN_PREFIX = "passwordResetCooldown."


class EmailOtpService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = UserRepository(session)

    async def send_verification_code(
        self,
        user: User,
        email: str | None = None,
        *,
        resend: bool = True,
    ) -> str:
        target_email = self._normalize_email(email or user.email)
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите электронную почту",
            )

        current = self._normalize_email(user.email)
        if target_email != current:
            user.email = target_email
            user.email_verified = False
            await self.session.flush()
            await self.session.commit()
            await self.session.refresh(user)
            await self.invalidate_verification(user.id)

        if user.email_verified and current == target_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Почта уже подтверждена",
            )

        if not resend:
            pending_email = await self._pending_verification_email(user.id)
            if pending_email == target_email:
                return target_email

        cooldown_key = f"{VERIFY_COOLDOWN_PREFIX}{user.id}"
        await self._assert_cooldown(cooldown_key)
        code = self._generate_code()
        await self._store_challenge(
            f"{VERIFY_KEY_PREFIX}{user.id}",
            {
                "code": code,
                "email": target_email,
                "attempts": 0,
            },
        )
        await redis_client.set(
            cooldown_key,
            "1",
            ex=SEND_COOLDOWN_SECONDS,
        )
        try:
            await self._send_verification_mail(user, target_email, code)
        except Exception:
            await redis_client.delete(cooldown_key)
            raise
        return target_email

    async def confirm_verification_code(
        self,
        user: User,
        code: str,
    ) -> User:
        if user.email_verified:
            return user

        payload = await self._consume_code(
            f"{VERIFY_KEY_PREFIX}{user.id}",
            code,
            missing_detail="Ссылка недействительна или уже использована",
        )
        stored_email = str(payload.get("email") or "")
        if stored_email and stored_email != self._normalize_email(user.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Код был отправлен на другую почту",
            )

        user.email_verified = True
        await self.session.commit()
        await self.session.refresh(user)
        await self.invalidate_verification(user.id)
        return user

    async def send_password_reset_code(self, email: str) -> None:
        target_email = self._normalize_email(email)
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите электронную почту",
            )

        cooldown_key = f"{RESET_COOLDOWN_PREFIX}{target_email}"
        await self._assert_cooldown(cooldown_key)

        user = await self.repo.get_by_email(target_email)
        await redis_client.set(
            cooldown_key,
            "1",
            ex=SEND_COOLDOWN_SECONDS,
        )
        if user is None:
            logger.info(
                "Password reset requested for unknown email"
            )
            return

        code = self._generate_code()
        await self._store_challenge(
            f"{RESET_KEY_PREFIX}{user.id}",
            {
                "code": code,
                "email": target_email,
                "attempts": 0,
            },
        )
        try:
            await self._send_reset_mail(user, target_email, code)
        except Exception:
            await redis_client.delete(cooldown_key)
            raise

    async def send_password_reset_for_user(self, user: User) -> str:
        target_email = self._normalize_email(user.email)
        if not target_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите электронную почту",
            )
        await self.send_password_reset_code(target_email)
        return target_email

    async def reset_password(
        self,
        *,
        user_id: int,
        code: str,
        new_password: str,
    ) -> User:
        user = await self.repo.get_user(UserSpec(id=user_id))
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ссылка недействительна или уже использована",
            )

        payload = await self._consume_code(
            f"{RESET_KEY_PREFIX}{user.id}",
            code,
            missing_detail="Ссылка недействительна или уже использована",
        )
        stored_email = str(payload.get("email") or "")
        if stored_email and stored_email != self._normalize_email(user.email):
            await redis_client.delete(f"{RESET_KEY_PREFIX}{user.id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ссылка недействительна или уже использована",
            )

        await self.repo.update_password_hash(
            user,
            security.hash_secret(new_password),
        )
        if stored_email and stored_email == self._normalize_email(user.email):
            user.email_verified = True
        await self.session.commit()
        await self.session.refresh(user)
        await redis_client.delete(f"{RESET_KEY_PREFIX}{user.id}")
        return user

    async def invalidate_verification(self, user_id: int) -> None:
        await redis_client.delete(f"{VERIFY_KEY_PREFIX}{user_id}")
        await redis_client.delete(f"{VERIFY_COOLDOWN_PREFIX}{user_id}")

    async def _pending_verification_email(self, user_id: int) -> str | None:
        raw = await redis_client.get(f"{VERIFY_KEY_PREFIX}{user_id}")
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        email = str(payload.get("email") or "").strip().lower()
        return email or None

    async def _send_verification_mail(
        self,
        user: User,
        email: str,
        code: str,
    ) -> None:
        name = user.first_name or user.username
        link = self._verification_link(user.id, code)
        await rusender.send_mail(
            to_email=email,
            to_name=user.full_name or name,
            subject="Подтверждение почты",
            html=self._link_html(
                title="Подтверждение почты",
                greeting=f"Здравствуйте, {name}!",
                lead=(
                    "Чтобы подтвердить электронную почту в магазине "
                    "Созвездие, нажмите на кнопку ниже."
                ),
                button_text="Подтвердить почту",
                link=link,
            ),
            idempotency_key=f"email-verify-{user.id}-{code}",
        )

    async def _send_reset_mail(
        self,
        user: User,
        email: str,
        code: str,
    ) -> None:
        name = user.first_name or user.username
        link = self._reset_link(user.id, code)
        await rusender.send_mail(
            to_email=email,
            to_name=user.full_name or name,
            subject="Смена пароля",
            html=self._link_html(
                title="Смена пароля",
                greeting=f"Здравствуйте, {name}!",
                lead=(
                    "Чтобы задать новый пароль в магазине Созвездие, "
                    "нажмите на кнопку ниже."
                ),
                button_text="Сменить пароль",
                link=link,
            ),
            idempotency_key=f"password-reset-{user.id}-{code}",
        )

    async def _assert_cooldown(self, key: str) -> None:
        if await redis_client.exists(key):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Повторная отправка будет доступна через минуту",
            )

    async def _store_challenge(
        self,
        key: str,
        payload: dict[str, Any],
    ) -> None:
        await redis_client.set(
            key,
            json.dumps(payload),
            ex=CODE_TTL_SECONDS,
        )

    async def _load_challenge(
        self,
        key: str,
        *,
        missing_detail: str,
    ) -> dict[str, Any]:
        raw = await redis_client.get(key)
        if not raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=missing_detail,
            )
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            await redis_client.delete(key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=missing_detail,
            ) from error
        if not isinstance(payload, dict):
            await redis_client.delete(key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=missing_detail,
            )
        return payload

    async def _save_challenge(
        self,
        key: str,
        payload: dict[str, Any],
    ) -> None:
        ttl = await redis_client.ttl(key)
        expire = ttl if isinstance(ttl, int) and ttl > 0 else CODE_TTL_SECONDS
        await redis_client.set(key, json.dumps(payload), ex=expire)

    async def _consume_code(
        self,
        key: str,
        code: str,
        *,
        missing_detail: str,
    ) -> dict[str, Any]:
        payload = await self._load_challenge(
            key,
            missing_detail=missing_detail,
        )
        attempts = int(payload.get("attempts") or 0)
        if attempts >= MAX_ATTEMPTS:
            await redis_client.delete(key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Слишком много попыток. Запросите код заново",
            )

        expected = str(payload.get("code") or "")
        submitted = self._normalize_code(code)
        if (
            not expected
            or len(submitted) != CODE_LENGTH
            or submitted != expected
        ):
            payload["attempts"] = attempts + 1
            if int(payload["attempts"]) >= MAX_ATTEMPTS:
                await redis_client.delete(key)
            else:
                await self._save_challenge(key, payload)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный код подтверждения",
            )
        return payload

    def _normalize_code(self, code: str) -> str:
        return "".join(ch for ch in code.strip() if ch.isdigit())

    def _normalize_email(self, email: str | None) -> str:
        return (email or "").strip().lower()

    def _generate_code(self) -> str:
        return f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"

    def _verification_link(self, user_id: int, code: str) -> str:
        base = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return f"{base}/verify-email?uid={user_id}&code={code}"

    def _reset_link(self, user_id: int, code: str) -> str:
        base = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
        return f"{base}/reset-password?uid={user_id}&code={code}"

    def _link_html(
        self,
        *,
        title: str,
        greeting: str,
        lead: str,
        button_text: str,
        link: str,
    ) -> str:
        safe_link = html.escape(link, quote=True)
        return f"""
<div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;
color:#132647;line-height:1.5">
  <h1 style="font-size:22px;margin:0 0 16px">{html.escape(title)}</h1>
  <p style="margin:0 0 12px">{html.escape(greeting)}</p>
  <p style="margin:0 0 20px">{html.escape(lead)}</p>
  <p style="margin:0 0 20px">
    <a href="{safe_link}" style="display:inline-block;padding:12px 24px;
    background:#4f83e3;color:#ffffff;border-radius:10px;text-decoration:none;
    font-weight:700">{html.escape(button_text)}</a>
  </p>
  <p style="margin:0 0 12px;font-size:13px;color:#6b7a90">
    Если кнопка не открывается, перейдите по ссылке:<br>
    <a href="{safe_link}" style="color:#4f83e3;word-break:break-all">
    {safe_link}</a>
  </p>
  <p style="margin:0 0 12px">Ссылка действует 10 минут. Если вы не
  запрашивали это письмо, просто проигнорируйте его.</p>
  <p style="margin:0">Команда Созвездие</p>
</div>
"""
