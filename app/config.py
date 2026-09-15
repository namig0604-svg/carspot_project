from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost/carspot_db"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # App
    APP_NAME: str = "CarSpot API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # CORS
    ALLOWED_ORIGINS: list = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8080",
    ]
    
    # File upload
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    UPLOAD_DIR: str = "./uploads"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
