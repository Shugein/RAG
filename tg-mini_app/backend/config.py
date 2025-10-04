# -*- coding: utf-8 -*-

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator

class Settings(BaseSettings):

    app_name: str = "RADAR Finance Mini App"
    debug: bool = False
    version: str = "1.0.0"
    
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_prefix: str = "/api"
    
    telegram_bot_token: Optional[str] = None
    telegram_webhook_url: Optional[str] = None
    telegram_webhook_secret: Optional[str] = None
    
    database_url: Optional[str] = None
    
    redis_url: str = "redis://localhost:6379/0"
    
    cors_origins: list = ["*"]
    cors_methods: list = ["*"]
    cors_headers: list = ["*"]
    
    radar_data_path: str = "../final_radar_data"
    moex_data_path: str = "../data"
    
    default_news_limit: int = 20
    max_news_limit: int = 100
    search_results_limit: int = 50
    
    cache_ttl: int = 300 
    enable_cache: bool = True
    
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    @field_validator('cors_origins', 'cors_methods', 'cors_headers')
    @classmethod
    def parse_list(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()

DEV_CONFIG = {
    "debug": True,
    "log_level": "DEBUG",
    "enable_cache": False,
    "cors_origins": ["*"],
}

PROD_CONFIG = {
    "debug": False,
    "log_level": "WARNING",
    "enable_cache": True,
    "cors_origins": ["https://your-domain.com"],
}

def get_config():
    if settings.debug:
        return {**settings.dict(), **DEV_CONFIG}
    return {**settings.dict(), **PROD_CONFIG}