import json

from app.utils.form_bool import parse_form_bool


def parse_image_slots_payload(image_slots: str) -> tuple[list, bool | None]:
    payload = json.loads(image_slots)
    if isinstance(payload, dict):
        slots = payload.get("slots", payload.get("image_slots"))
        if not isinstance(slots, list):
            raise TypeError("Invalid image_slots payload")
        if "is_adult" in payload or "isAdult" in payload:
            return slots, parse_form_bool(
                payload.get("is_adult", payload.get("isAdult"))
            )
        return slots, None
    if isinstance(payload, list):
        return payload, None
    raise TypeError("Invalid image_slots payload")


def parse_flags_is_adult(flags: str | None) -> bool | None:
    if not flags or not str(flags).strip():
        return None
    try:
        payload = json.loads(flags)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if "is_adult" not in payload and "isAdult" not in payload:
        return None
    return parse_form_bool(payload.get("is_adult", payload.get("isAdult")))


def _explicit_bool(value: str | bool | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return parse_form_bool(value)


def resolve_is_adult(
    *,
    form_value: str | bool | None = None,
    query_value: str | bool | None = None,
    form_adult: str | bool | None = None,
    slots_adult: bool | None = None,
    flags_adult: bool | None = None,
) -> bool:
    explicit = [
        value
        for value in (
            _explicit_bool(query_value),
            _explicit_bool(form_adult),
            flags_adult,
            slots_adult,
            _explicit_bool(form_value),
        )
        if value is not None
    ]
    if not explicit:
        return False
    return any(explicit)
