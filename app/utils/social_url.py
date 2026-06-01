def normalize_optional_url(value: str | None) -> str | None:
    if value is None:
        return None

    trimmed = value.strip()
    if not trimmed:
        return None

    if not trimmed.startswith(("http://", "https://")):
        return f"https://{trimmed}"

    return trimmed
