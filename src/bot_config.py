from pydantic import Field
from pydantic_settings import BaseSettings
from typing import List, get_type_hints
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Stock Info Bot"
    PROJECT_DESCRIPTION: str = "A Discord bot that provides stock information."
    PROJECT_VERSION: str = "1.0.0"

    # DEBUG 설정
    DEBUG: bool = Field(default=True, description="디버그 모드 활성화 여부")
    CORS_ORIGINS: List[str] = ["*"]

    SUPABASE_URL: str = Field(..., description="SUPABASE URL")
    SUPABASE_KEY: str = Field(..., description="SUPABASE API KEY")

    # DISCORD_URL: str = Field(..., description="디스코드 알림 URL")
    # DISCORD_COIN_URL: str = Field(..., description="디스코드 코인 알림 URL")
    DISCORD_BOT_TOKEN: str = Field(..., description="디스코드 봇 토큰")

    class Config:
        env_file = "../../.env"
        env_file_encoding = "utf-8"
        case_sensitive = True

# 싱글톤 설정 객체 생성
settings = Settings()