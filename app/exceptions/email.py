EMAIL_NOT_VERIFIED_CODE = "email_not_verified"
EMAIL_NOT_VERIFIED_MESSAGE = (
    "Подтвердите email, чтобы оформить заказ"
)


class EmailNotVerifiedError(ValueError):
    code = EMAIL_NOT_VERIFIED_CODE

    def __init__(self, message: str = EMAIL_NOT_VERIFIED_MESSAGE) -> None:
        super().__init__(message)


def require_verified_email(
    *,
    email: str | None,
    email_verified: bool,
) -> None:
    if not (email or "").strip() or not email_verified:
        raise EmailNotVerifiedError()

