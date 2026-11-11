from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")
    database_url: str = "sqlite:///data/database.db"
    pluggy_client_id: str = ""
    pluggy_client_secret: str = ""
    pluggy_base_url: str = "https://api.pluggy.ai"
    pluggy_item_id: str = ""   # ou None



settings = Settings()

DATABASE_URL = settings.database_url
PLUGGY_CLIENT_ID = settings.pluggy_client_id
PLUGGY_CLIENT_SECRET = settings.pluggy_client_secret
PLUGGY_BASE_URL = settings.pluggy_base_url