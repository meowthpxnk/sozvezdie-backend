from dataclasses import dataclass


@dataclass
class ProductSpec:
    id: int | None = None
    ids: list[int] | None = None
    seller_card_id: str | None = None
    include_images: bool = True
    include_inventory: bool = True
    include_seller_card: bool = True
    include_subcategory: bool = True
    include_moderations: bool = False
    all: bool = False
    approved_only: bool = False

    def __post_init__(self):
        if self.include_images:
            self.include_images = True
        if self.include_inventory:
            self.include_inventory = True
        if self.include_seller_card:
            self.include_seller_card = True
