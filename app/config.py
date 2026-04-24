import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    APPLICATION_ROOT = os.environ.get("APPLICATION_ROOT", "/")

    GHOSTWRITER_URL = os.environ.get("GHOSTWRITER_URL", "")
    GHOSTWRITER_VERIFY_SSL = os.environ.get("GHOSTWRITER_VERIFY_SSL", "true").lower() not in ("false", "0", "no")
    GHOSTWRITER_CF_CLIENT_ID     = os.environ.get("GHOSTWRITER_CF_CLIENT_ID", "")
    GHOSTWRITER_CF_CLIENT_SECRET = os.environ.get("GHOSTWRITER_CF_CLIENT_SECRET", "")

    RENDER_LANGUAGE = os.environ.get("RENDER_LANGUAGE", "en")

    VAULTWARDEN_URL           = os.environ.get("VAULTWARDEN_URL", "")
    VAULTWARDEN_ORG_ID        = os.environ.get("VAULTWARDEN_ORG_ID", "")
    VAULTWARDEN_COLLECTION_ID = os.environ.get("VAULTWARDEN_COLLECTION_ID", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
