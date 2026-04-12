from pydantic_settings import BaseSettings, SettingsConfigDict


class Setting(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 是否启用上下文压缩
    CONTEXT_COMPACTION_ENABLED: bool = True
    # 超过该消息条数后触发一次压缩
    CONTEXT_COMPACTION_TRIGGER_MESSAGES: int = 25
    # 每次压缩后保留最近 N 条原始消息，避免丢失短期语境
    CONTEXT_COMPACTION_KEEP_RECENT_MESSAGES: int = 10
    # 参与压缩的历史文本最大长度（字符）
    CONTEXT_COMPACTION_MAX_TRANSCRIPT_CHARS: int = 120000
    # 摘要消息前缀，用于识别历史摘要并做增量更新
    CONTEXT_COMPACTION_SUMMARY_TAG: str = "[CONTEXT_BRIEF]"


context_compaction_setting = Setting()  # type: ignore