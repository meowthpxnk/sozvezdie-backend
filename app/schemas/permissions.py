import enum

from app.schemas.database import UserRoleEnum

class PermissionEnum(str, enum.Enum):
    DEVICE_READ = "device:read"
    DEVICE_READ_ENTITY = "device:read_entity"
    DEVICE_CREATE = "device:create"
    DEVICE_DELETE = "device:delete"
    DEVICE_EDIT = "device:edit"
    DEVICE_START = "device:start"
    DEVICE_STOP = "device:stop"
    DEVICE_RELOAD = "device:reload"

    SERVER_READ = "server:read"
    SERVER_CREATE = "server:create"
    SERVER_DELETE = "server:delete"

    IMAGE_READ = "image:read"
    IMAGE_CREATE = "image:create"
    IMAGE_DELETE = "image:delete"

    APIKEY_LIST = "apikey:list"
    APIKEY_CREATE = "apikey:create"
    APIKEY_DELETE = "apikey:delete"
    APIKEY_READ = "apikey:read"
    APIKEY_CHANGE_PERMISSIONS = "apikey:change_permissions"

    SESSION_CLOSE = "session:close"
    SESSION_LOGOUT = "session:logout"
    SESSION_PAYLOAD = "session:payload"

    USER_CREATE = "user:create"
    USER_EDIT = "user:edit"
    USER_DELETE = "user:delete"
    USER_READ = "user:read"
    USER_SETTINGS_READ = "user_settings:read"
    USER_SETTINGS_EDIT = "user_settings:edit"

    PRODUCT_CREATE = "product:create"
    PRODUCT_READ = "product:read"
    PRODUCT_DELETE = "product:delete"
    PRODUCT_INVENTORY_EDIT = "product_inventory:edit"
    PRODUCT_IMAGE_EDIT = "product_image:edit"
    PRODUCT_ALTERNATIVE_EDIT = "product_alternative:edit"
    PRODUCT_MODERATION_EDIT = "product_moderation:edit"

    CART_READ = "cart:read"
    CART_EDIT = "cart:edit"

    ORDER_CREATE = "order:create"
    ORDER_READ = "order:read"
    ORDER_EDIT = "order:edit"
    ORDER_DELETE = "order:delete"

    REVIEW_CREATE = "review:create"
    REVIEW_DELETE = "review:delete"

    SELLER_CARD_CREATE = "seller_card:create"
    SELLER_CARD_READ = "seller_card:read"
    SELLER_CARD_EDIT = "seller_card:edit"
    SELLER_CARD_DELETE = "seller_card:delete"


# BASIC_ROLE_PERMISSIONS: dict[UserRoleEnum, set[str]] = {
#     UserRoleEnum.SUPPORT: {
#         PermissionEnum.DEVICE_CREATE,
#         PermissionEnum.DEVICE_READ,
#     },
#     UserRoleEnum.SUPERVISOR: {
#         PermissionEnum.DEVICE_READ,
#         PermissionEnum.DEVICE_READ_ENTITY,
#         PermissionEnum.DEVICE_CREATE,
#         PermissionEnum.DEVICE_EDIT,
#         PermissionEnum.SERVER_READ,
#         PermissionEnum.SERVER_CREATE,
#         PermissionEnum.IMAGE_READ,
#         PermissionEnum.IMAGE_CREATE,
#     },
#     UserRoleEnum.ADMIN: {"*"},
# }
