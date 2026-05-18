from dataclasses import dataclass


@dataclass
class CartSpec:
    user_id: int
    include_items: bool = False
    include_product_details: bool = False
