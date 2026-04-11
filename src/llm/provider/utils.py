from typing import Any

from openai import (
	APIConnectionError,
	APIStatusError,
	APITimeoutError,
	AuthenticationError,
	PermissionDeniedError,
	RateLimitError,
)

from src.core.exceptions import ExternalServiceException


def _safe_lower(value: Any) -> str:
	"""将任意值安全转换为小写字符串。"""
	if value is None:
		return ""
	return str(value).strip().lower()


def _extract_openai_error_payload(exc: Exception) -> dict[str, Any]:
	"""提取 OpenAI 异常中的错误负载，兼容 body.error 嵌套结构。"""
	body = getattr(exc, "body", None)
	if not isinstance(body, dict):
		return {}

	nested_error = body.get("error")
	if isinstance(nested_error, dict):
		return nested_error

	return body


def classify_openai_error(exc: Exception) -> tuple[str, str]:
	"""将 OpenAI SDK 异常映射为项目业务错误类型与用户提示。"""
	payload = _extract_openai_error_payload(exc)

	status_code = getattr(exc, "status_code", None)
	status_code = status_code if isinstance(status_code, int) else 0

	raw_message = _safe_lower(exc)
	payload_message = _safe_lower(payload.get("message"))
	payload_code = _safe_lower(payload.get("code") or getattr(exc, "code", None))
	payload_type = _safe_lower(payload.get("type") or getattr(exc, "type", None))

	timeout_keywords = ("timeout", "timed out")
	if isinstance(exc, APITimeoutError) or any(k in raw_message for k in timeout_keywords):
		return "timeout", "LLM 服务响应超时，请稍后再试"

	if isinstance(exc, APIConnectionError):
		return "connection_error", "无法连接 LLM 服务，请检查网络或服务地址"

	quota_keywords = (
		"insufficient_quota",
		"quota_exceeded",
		"quota",
		"rate_limit",
		"rate limit",
		"arrearage",
		"overdue-payment",
		"billing",
	)
	quota_text = " ".join((payload_code, payload_type, payload_message, raw_message))
	if isinstance(exc, RateLimitError) or status_code == 429 or any(k in quota_text for k in quota_keywords):
		return "quota_exceeded", "账户额度不足或已欠费，请充值后重试"

	auth_keywords = ("authentication", "api key", "unauthorized", "permission", "forbidden")
	auth_text = " ".join((payload_code, payload_type, payload_message, raw_message))
	if (
		isinstance(exc, (AuthenticationError, PermissionDeniedError))
		or status_code in (401, 403)
		or any(k in auth_text for k in auth_keywords)
	):
		return "auth_error", "API Key 无效、已过期或无权限，请检查模型配置"

	if isinstance(exc, APIStatusError) and status_code >= 500:
		return "llm_error", "LLM 服务暂时不可用，请稍后再试"

	return "llm_error", "LLM 服务异常，请稍后再试"


def to_external_service_exception(exc: Exception, *, code: int = 5001) -> ExternalServiceException:
	"""将 OpenAI 异常转换为项目统一的 ExternalServiceException。"""
	error_type, user_message = classify_openai_error(exc)
	details: dict[str, Any] = {"error_type": error_type}

	request_id = getattr(exc, "request_id", None)
	if request_id:
		details["request_id"] = request_id

	status_code = getattr(exc, "status_code", None)
	if isinstance(status_code, int):
		details["provider_status_code"] = status_code

	return ExternalServiceException(
		message=user_message,
		code=code,
		details=details,
	)
