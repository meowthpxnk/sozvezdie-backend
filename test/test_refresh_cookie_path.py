from app.settings import JWTAuthSettings


def test_refresh_cookie_path_local_default():
    settings = JWTAuthSettings(API_ROOT_PATH="")
    assert settings.refresh_cookie_path() == "/refresh-session"


def test_refresh_cookie_path_with_api_prefix():
    settings = JWTAuthSettings(API_ROOT_PATH="/api")
    assert settings.refresh_cookie_path() == "/api/refresh-session"


def test_refresh_cookie_path_strips_trailing_slash():
    settings = JWTAuthSettings(API_ROOT_PATH="/api/")
    assert settings.refresh_cookie_path() == "/api/refresh-session"
