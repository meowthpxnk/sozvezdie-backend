INSUFFICIENT_STOCK_CODE = "insufficient_stock"
INSUFFICIENT_STOCK_MESSAGE = "Некоторые товары закончились. Проверьте корзину."


class InsufficientStockError(ValueError):
    code = INSUFFICIENT_STOCK_CODE

    def __init__(self, message: str = INSUFFICIENT_STOCK_MESSAGE) -> None:
        super().__init__(message)
