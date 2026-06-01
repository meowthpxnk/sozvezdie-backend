from fastapi import HTTPException, status

from app.exceptions.order import InsufficientStockError


def raise_http_for_order_error(error: ValueError) -> None:
    if isinstance(error, InsufficientStockError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": error.code,
                "message": str(error),
            },
        ) from error
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=str(error),
    ) from error
