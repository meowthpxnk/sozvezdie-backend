import re


def camel_to_snake(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()


def format_person_name(
    last_name: str | None,
    first_name: str | None,
    patronymic: str | None,
) -> str | None:
    parts = [
        part.strip()
        for part in (last_name, first_name, patronymic)
        if part and part.strip()
    ]
    return " ".join(parts) or None
