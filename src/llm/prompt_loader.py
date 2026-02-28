from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(prompt_file_name: str) -> str:
    """读取 prompts 目录下的提示词文件内容。"""
    prompt_path = _PROMPTS_DIR / prompt_file_name
    try:
        return prompt_path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}") from e
