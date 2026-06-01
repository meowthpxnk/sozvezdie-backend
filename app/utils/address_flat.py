import re

FLAT_PATTERNS = (
    re.compile(r"(?:^|[\s,])кв\.?\s*([0-9]+[а-яА-Яa-zA-Z/-]*)", re.IGNORECASE),
    re.compile(r"(?:^|[\s,])квартира\s*([0-9]+[а-яА-Яa-zA-Z/-]*)", re.IGNORECASE),
    re.compile(r"(?:^|[\s,])apt\.?\s*([0-9]+[а-яА-Яa-zA-Z/-]*)", re.IGNORECASE),
)


def extract_flat_from_text(text: str | None) -> str | None:
    if not text or not text.strip():
        return None
    for pattern in FLAT_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def require_flat_for_courier(formatted_address: str) -> str:
    flat = extract_flat_from_text(formatted_address)
    if not flat:
        raise ValueError(
            "Укажите квартиру в адресе (например: ул. Примерная, 1, кв. 12)"
        )
    return flat
