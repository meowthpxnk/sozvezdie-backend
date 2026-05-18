from dataclasses import dataclass


@dataclass
class UserSpec:
    username: str | None = None
    id: int | None = None
    include_settings: bool = False
    include_orders: bool = False
    include_seller_card: bool = False
    include_cart: bool = False
