import os

from app.schemas.database import UserRoleEnum

TRUE_VALUES = {"1", "true", "yes", "on"}


def is_blocked_1c_users_enabled() -> bool:
    value = os.getenv("BLOCKED_1C_USERS", "false").strip().lower()
    return value in TRUE_VALUES


def is_user_blocked_without_1c(*, role: UserRoleEnum | str, one_c_author_id: str | None) -> bool:
    role_value = role.value if isinstance(role, UserRoleEnum) else role
    has_one_c = bool((one_c_author_id or "").strip())
    return (
        is_blocked_1c_users_enabled()
        and role_value == UserRoleEnum.SELLER.value
        and not has_one_c
    )


def seller_user_has_one_c_id(product) -> bool:
    seller_card = product.__dict__.get("seller_card")
    if seller_card is None:
        return True
    user = seller_card.__dict__.get("user")
    if user is None:
        return True
    return bool((user.one_c_author_id or "").strip())


def seller_shop_is_disabled(product) -> bool:
    seller_card = product.__dict__.get("seller_card")
    if seller_card is None:
        return False
    return bool(getattr(seller_card, "is_disabled", False))
