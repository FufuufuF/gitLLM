import logging
import re

from src.domain.models import ModelConfig
from src.llm.factory import get_model
from src.llm.prompt_loader import load_prompt

logger = logging.getLogger(__name__)

class SessionTitleService:
    """会话标题生成服务（独立于 ChatService 的业务编排）。"""

    def __init__(self) -> None:
        pass

    def _load_prompt(self) -> str:
        try:
            return load_prompt("generate_title.md")
        except FileNotFoundError:
            logger.warning("Title prompt file not found: generate_title.md")
            return "请根据用户首条消息生成一个简洁中文标题，仅输出标题。"

    def _fallback_title(self, first_user_message: str) -> str:
        text = re.sub(r"\s+", " ", first_user_message).strip()
        if not text:
            return "新会话"
        return text

    def _normalize_title(self, title: str) -> str:
        normalized = title.strip()
        normalized = re.sub(r"^['\"“”‘’]+|['\"“”‘’]+$", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.replace("\n", " ").replace("\r", " ").strip()
        return normalized

    async def generate_title(self, first_user_message: str, model_config: ModelConfig) -> str:
        """根据首条用户消息生成会话标题，失败时回退到本地兜底规则。"""
        fallback_title = self._fallback_title(first_user_message)
        prompt = self._load_prompt()
        final_prompt = (
            f"{prompt}\n\n"
            "【用户首条消息】\n"
            f"{first_user_message}\n\n"
            "【请输出标题】"
        )

        try:
            model = get_model(
                {
                    "provider": (model_config.provider or "tongyi").lower(),
                    "api_key": model_config.api_key,
                    "model_name": model_config.model_name,
                    "base_url": model_config.base_url,
                }
            )
            result = await model.ainvoke(final_prompt)
            title = self._normalize_title(str(result.content))
            print(f"Generated title: '{title}' from message: '{first_user_message}'")
            return title or fallback_title
        except Exception as e:
            logger.warning("Failed to generate session title via LLM: %s", e)
            return fallback_title
