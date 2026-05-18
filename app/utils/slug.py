import re

_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def translit_to_slug(text: str) -> str:
    normalized = text.strip().lower().replace("ё", "е")
    result: list[str] = []

    for char in normalized:
        if char in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[char])
            continue

        if char.isascii() and char.isalnum():
            result.append(char)
            continue

        if char in {" ", "-", "_"}:
            result.append("-")

    slug = "".join(result)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def validate_slug(slug: str) -> str:
    value = slug.strip().lower()
    if not _SLUG_RE.fullmatch(value):
        raise ValueError(
            "Slug must contain only lowercase latin letters, digits and hyphens"
        )
    return value
