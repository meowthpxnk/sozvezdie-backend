import secrets
import string

from app.schemas.schemas import validate_password_strength


def generate_random_password(length: int = 16) -> str:
    if length < 8:
        raise ValueError("Password length must be at least 8")

    alphabet = string.ascii_letters + string.digits

    for _ in range(50):
        chars = [
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.digits),
        ]
        chars.extend(secrets.choice(alphabet) for _ in range(length - 3))
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        try:
            return validate_password_strength(password)
        except ValueError:
            continue

    raise RuntimeError("Failed to generate a valid random password")
