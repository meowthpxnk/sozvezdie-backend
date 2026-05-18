import enum


class UserRoleEnum(enum.Enum):
    MODERATOR = "MODERATOR"
    CUSTOMER = "CUSTOMER"
    SELLER = "SELLER"


class AppTheme(enum.Enum):
    DARK = "DARK"
    LIGHT = "LIGHT"


class ModerationStatus(enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class OrderStatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELED = "CANCELED"


class PaymentMethod(enum.Enum):
    CARD_ONLINE = "CARD_ONLINE"
    ON_RECEIPT = "ON_RECEIPT"


class DeliveryMethod(enum.Enum):
    COURIER = "COURIER"
    PICKUP_POINT = "PICKUP_POINT"
    POST = "POST"
