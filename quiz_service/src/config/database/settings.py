from pydantic import PostgresDsn, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Database configuration environment variables.
    
    Provides the core DSN assembly and SQLAlchemy engine performance tunings
    such as connection pool sizes and query logging flags.
    """
    db_url_scheme: str = Field("postgresql+asyncpg", alias="DB_URL_SCHEME")
    db_host: str = Field("localhost", alias="DB_HOST")
    db_port: str = Field("5432", alias="DB_PORT")
    db_name: str = Field("test_db", alias="DB_NAME")
    
    db_user: str = Field("test_user", alias="DB_USER")
    db_password: str = Field("test_password", alias="DB_PASSWORD")
    
    db_echo_log: bool = Field(False, alias="DB_ECHO_LOG")
    db_run_auto_migrate: bool = Field(False, alias="DB_RUN_AUTO_MIGRATE")
    
    db_pool_size: int = Field(5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(10, alias="DB_MAX_OVERFLOW")

    @property
    def database_url(self) -> PostgresDsn | str:
        """URL to connect (DSN)"""
        return (
            f"{self.db_url_scheme}://{self.db_user}:{self.db_password}@"
            f"{self.db_host}:{self.db_port}/{self.db_name}"
        )


settings = Settings()
