import hashlib
import json

from app.schemas.api.responses import OrderCreateRequest


def build_cart_fingerprint(data: OrderCreateRequest) -> str:
    items = sorted(
        (
            {"product_id": item.product_id, "quantity": item.quantity}
            for item in data.items
        ),
        key=lambda x: (x["product_id"], x["quantity"]),
    )
    address_key = None
    if data.address is not None:
        address_key = {
            "formatted_address": data.address.formatted_address,
            "pvz_code": data.address.pvz_code,
            "lat": data.address.lat,
            "lon": data.address.lon,
        }
    payload = {
        "delivery_method": data.delivery_method.value,
        "delivery_cost": data.delivery_cost,
        "delivery_date": data.delivery_date.isoformat() if data.delivery_date else None,
        "items": items,
        "address": address_key,
        "checkout_session_id": data.checkout_session_id,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()
