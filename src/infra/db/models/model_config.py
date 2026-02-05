from __future__ import annotations
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.infra.db.models.base import MyORMBase

class ModelConfig(MyORMBase):
    __tablename__ = "model_configs"

    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="LLM Provider e.g. openai, azure")
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="API Base URL")
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, comment="Specific model name e.g. gpt-4")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
