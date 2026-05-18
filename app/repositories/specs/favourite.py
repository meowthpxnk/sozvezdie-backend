from dataclasses import dataclass


@dataclass
class FavouriteSpec:
    user_id: int
    product_id: int | None = None
    seller_card_id: int | None = None
