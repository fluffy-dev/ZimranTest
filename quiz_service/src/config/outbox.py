from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    poll_interval: float = Field(2.0, alias="OUTBOX_POLL_INTERVAL")
    batch_size: int = Field(50, alias="OUTBOX_BATCH_SIZE")

settings = Settings()
