from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_expire_minutes: int = Field(default=480, alias="JWT_EXPIRE_MINUTES")

    daraja_consumer_key: str = Field(default="", alias="DARAJA_CONSUMER_KEY")
    daraja_consumer_secret: str = Field(default="", alias="DARAJA_CONSUMER_SECRET")
    daraja_shortcode: str = Field(default="", alias="DARAJA_SHORTCODE")
    daraja_passkey: str = Field(default="", alias="DARAJA_PASSKEY")
    daraja_env: str = Field(default="production", alias="DARAJA_ENV")
    daraja_callback_base_url: str = Field(default="", alias="DARAJA_CALLBACK_BASE_URL")
    daraja_stk_transaction_type: str = Field(
        default="CustomerPayBillOnline", alias="DARAJA_STK_TRANSACTION_TYPE"
    )
    daraja_b2b_receiver_shortcode: str = Field(
        default="", alias="DARAJA_B2B_RECEIVER_SHORTCODE"
    )
    daraja_initiator_name: str = Field(default="", alias="DARAJA_INITIATOR_NAME")
    daraja_initiator_password: str = Field(default="", alias="DARAJA_INITIATOR_PASSWORD")

    sms_api_key: str = Field(default="", alias="SMS_API_KEY")
    sms_api_sender_id: str = Field(default="", alias="SMS_API_SENDER_ID")

    platform_fee_percent: float = Field(default=5.0, alias="PLATFORM_FEE_PERCENT")
    booking_lock_minutes: int = Field(default=5, alias="BOOKING_LOCK_MINUTES")

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
