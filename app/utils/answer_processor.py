"""
OCS网课助手答题处理器
支持手动题库→AI的查询顺序（不保存结果到数据库/缓存）
手动题库在读取3次后缓存到内存，并监控文件变化自动更新缓存
"""
import asyncio
import aiohttp
import json
import os
import threading
from typing import Optional, Dict, Any, AsyncIterator
from app.schemas.answer import OCSQuestionContext
from app.core.config import settings
from app.utils.logger import logger
from app.utils.question_detector import detect_question_type, clean_question_text, normalize_answer_for_type, normalize_question_type
from app.utils.http_client import get_http_session

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    logger.warning("watchdog 未安装，文件监控功能不可用。请运行: pip install watchdog")


# 手动题库文件路径
MANUAL_QUESTION_BANK_PATH = "manual_question_bank.json"

# 缓存相关变量
_question_bank_cache: Optional[Dict[str, Dict[str, str]]] = None
_cache_read_count: int = 0
_cache_threshold: int = 3  # 读取3次后启用缓存
_cache_lock = threading.Lock()
_file_observer: Optional[Any] = None


class QuestionBankFileHandler(FileSystemEventHandler):
    """手动题库文件变化处理器"""

    def on_modified(self, event):
        if event.is_directory:
            return
        # 检查是否是目标文件
        if os.path.basename(event.src_path) == os.path.basename(MANUAL_QUESTION_BANK_PATH):
            logger.info(f"检测到手动题库文件变化，重新加载缓存: {event.src_path}")
            _reload_cache()


def _reload_cache():
    """重新加载缓存"""
    global _question_bank_cache
    with _cache_lock:
        try:
            if os.path.exists(MANUAL_QUESTION_BANK_PATH):
                with open(MANUAL_QUESTION_BANK_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    _question_bank_cache = data if isinstance(data, dict) else {}
                    logger.info(f"手动题库缓存已更新，共 {len(_question_bank_cache)} 条记录")
            else:
                _question_bank_cache = {}
        except Exception as e:
            logger.error(f"重新加载手动题库缓存失败: {e}")


def _start_file_watcher():
    """启动文件监控"""
    global _file_observer
    if not WATCHDOG_AVAILABLE:
        logger.warning("watchdog 不可用，无法启动文件监控")
        return

    if _file_observer is not None:
        return  # 已经启动

    try:
        watch_path = os.path.dirname(os.path.abspath(MANUAL_QUESTION_BANK_PATH)) or "."
        event_handler = QuestionBankFileHandler()
        _file_observer = Observer()
        _file_observer.schedule(event_handler, watch_path, recursive=False)
        _file_observer.daemon = True
        _file_observer.start()
        logger.info(f"已启动手动题库文件监控: {watch_path}")
    except Exception as e:
        logger.error(f"启动文件监控失败: {e}")


def load_manual_question_bank() -> Dict[str, Dict[str, str]]:
    """加载手动题库（带缓存机制）"""
    global _question_bank_cache, _cache_read_count

    with _cache_lock:
        # 如果已有缓存，直接返回
        if _question_bank_cache is not None:
            logger.debug("从内存缓存读取手动题库")
            return _question_bank_cache

        # 增加读取计数
        _cache_read_count += 1

        try:
            if os.path.exists(MANUAL_QUESTION_BANK_PATH):
                with open(MANUAL_QUESTION_BANK_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    result = data if isinstance(data, dict) else {}

                    # 达到阈值后启用缓存
                    if _cache_read_count >= _cache_threshold:
                        _question_bank_cache = result
                        logger.info(f"手动题库已缓存到内存（第 {_cache_read_count} 次读取），共 {len(result)} 条记录")
                        # 启动文件监控
                        _start_file_watcher()
                    else:
                        logger.debug(f"从文件读取手动题库（第 {_cache_read_count}/{_cache_threshold} 次）")

                    return result
        except Exception as e:
            logger.error(f"加载手动题库失败: {e}")
        return {}


def query_manual_question_bank_sync(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """
    同步查询手动题库
    支持题目+类型精确匹配，以及题目模糊匹配
    数据格式: {"题目": {"answer": "答案", "type": "single", "note": "备注"}}
    """
    try:
        bank = load_manual_question_bank()
        question_key = question_context.title.strip()
        request_type = question_context.type or ""

        # 1. 优先：题目+类型精确匹配（相同题目不同题型）
        if request_type and question_key in bank:
            answer_data = bank[question_key]
            if isinstance(answer_data, dict) and answer_data.get('type') == request_type:
                answer = answer_data.get('answer', '')
                result_type = answer_data.get('type', request_type)
                logger.info(f"从手动题库找到答案（精确匹配）: {question_key}, 类型: {result_type}")
                return {
                    "question": question_key,
                    "answer": answer,
                    "question_type": result_type,
                    "source": "manual",
                    "confidence": 1.0,
                    "metadata": {"source": "manual_question_bank", "match_type": "exact_with_type"}
                }

        # 2. 其次：题目精确匹配（忽略类型）
        if question_key in bank:
            answer_data = bank[question_key]
            if isinstance(answer_data, dict):
                answer = answer_data.get('answer', '')
                result_type = answer_data.get('type', request_type) or "single"
                logger.info(f"从手动题库找到答案（题目匹配）: {question_key}, 类型: {result_type}")
                return {
                    "question": question_key,
                    "answer": answer,
                    "question_type": result_type,
                    "source": "manual",
                    "confidence": 1.0,
                    "metadata": {"source": "manual_question_bank", "match_type": "exact"}
                }
            else:
                # 兼容旧格式：直接是答案字符串
                logger.info(f"从手动题库找到答案（旧格式）: {question_key}")
                return {
                    "question": question_key,
                    "answer": answer_data,
                    "question_type": request_type or "single",
                    "source": "manual",
                    "confidence": 1.0,
                    "metadata": {"source": "manual_question_bank", "match_type": "exact_legacy"}
                }

        # 3. 最后：模糊匹配（标题包含请求的题目）
        for bank_key, answer_data in bank.items():
            if question_key in bank_key or bank_key in question_key:
                if isinstance(answer_data, dict):
                    answer = answer_data.get('answer', '')
                    result_type = answer_data.get('type', request_type) or "single"
                    logger.info(f"从手动题库找到答案（模糊匹配）: {bank_key} -> {question_key}")
                    return {
                        "question": bank_key,
                        "answer": answer,
                        "question_type": result_type,
                        "source": "manual",
                        "confidence": 0.9,
                        "metadata": {"source": "manual_question_bank", "match_type": "fuzzy"}
                    }

    except Exception as e:
        logger.error(f"查询手动题库出错: {e}")
    return None


async def query_manual_question_bank(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """手动题库查询（异步包装）"""
    return query_manual_question_bank_sync(question_context)


_ANSWER_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"}
    },
    "required": ["answer"],
    "additionalProperties": False
}


def _normalize_provider(provider: str) -> str:
    provider_key = (provider or "").strip().lower()
    provider_aliases = {
        "openai": "openai_chat_completions",
        "openai_chat": "openai_chat_completions",
        "openai_chat_completions": "openai_chat_completions",
        "openai_responses": "openai_responses",
        "responses": "openai_responses",
        "dashscope": "dashscope",
        "anthropic": "anthropic",
        "claude": "anthropic"
    }
    return provider_aliases.get(provider_key, provider_key or "openai_chat_completions")


def _get_thinking_value(question_context: OCSQuestionContext) -> Optional[bool]:
    env_value = settings.AI_ENABLE_THINKING_PARAMS
    if env_value is None:
        return None
    if question_context.thinking is not None:
        return question_context.thinking
    return env_value


def _thinking_enabled(question_context: OCSQuestionContext) -> bool:
    return _get_thinking_value(question_context) is True


def _get_thinking_budget(question_context: OCSQuestionContext, default_budget: int = 512) -> int:
    budget = question_context.thinking_budget
    if isinstance(budget, int) and budget > 0:
        return budget
    return default_budget


def _get_max_output_tokens(default_value: int = 1000) -> int:
    configured_value = getattr(settings, "AI_MAX_OUTPUT_TOKENS", default_value)
    if isinstance(configured_value, int) and configured_value > 0:
        return configured_value
    return default_value


def _openai_supports_reasoning_none(model_name: str) -> bool:
    normalized_name = (model_name or "").strip().lower()
    if not normalized_name.startswith("gpt-5"):
        return False
    if normalized_name.startswith("gpt-5."):
        return True
    return False


def _structured_output_enabled(question_context: OCSQuestionContext) -> bool:
    return bool(question_context.structured_output and settings.AI_ENABLE_STRUCTURED_OUTPUT_PARAMS)


def _streaming_enabled(question_context: OCSQuestionContext) -> bool:
    return bool(question_context.stream and settings.AI_ENABLE_STREAMING_PARAMS)


def _join_url(base_url: str, path: str) -> str:
    base = (base_url or "").rstrip("/")
    suffix = path.lstrip("/")
    if base.endswith(suffix):
        return base
    return f"{base}/{suffix}"


def _dashscope_endpoint(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    full_suffix = "api/v1/services/aigc/text-generation/generation"
    path_suffix = "services/aigc/text-generation/generation"

    if base.endswith(full_suffix):
        return base
    if base.endswith(path_suffix):
        base_root = base[:-len(path_suffix)].rstrip("/")
        return _join_url(base_root, full_suffix)
    if base.endswith("api/v1"):
        return _join_url(base, path_suffix)
    return _join_url(base, full_suffix)


def _anthropic_endpoint(base_url: str) -> str:
    return _join_url(base_url, "messages")


def _openai_chat_endpoint(base_url: str) -> str:
    return _join_url(base_url, "chat/completions")


def _openai_responses_endpoint(base_url: str) -> str:
    return _join_url(base_url, "responses")


def _apply_openai_chat_thinking_settings(data: Dict[str, Any], question_context: OCSQuestionContext) -> str:
    thinking_value = _get_thinking_value(question_context)
    if thinking_value is None:
        return "not_forwarded"
    if thinking_value is True:
        data["reasoning_effort"] = "high"
        return "enabled"
    if _openai_supports_reasoning_none(settings.AI_MODEL_NAME):
        data["reasoning_effort"] = "none"
        return "disabled"
    logger.info(f"OpenAI Chat 当前模型不支持 reasoning_effort=none，跳过关闭思考字段: model={settings.AI_MODEL_NAME}")
    return "disable_unsupported_skipped"


def _apply_openai_responses_thinking_settings(data: Dict[str, Any], question_context: OCSQuestionContext) -> str:
    thinking_value = _get_thinking_value(question_context)
    if thinking_value is None:
        return "not_forwarded"
    if thinking_value is True:
        data["reasoning"] = {"effort": "high"}
        return "enabled"
    if _openai_supports_reasoning_none(settings.AI_MODEL_NAME):
        data["reasoning"] = {"effort": "none"}
        return "disabled"
    logger.info(f"OpenAI Responses 当前模型不支持 reasoning.effort=none，跳过关闭思考字段: model={settings.AI_MODEL_NAME}")
    return "disable_unsupported_skipped"


def _apply_dashscope_thinking_settings(parameters: Dict[str, Any], question_context: OCSQuestionContext) -> str:
    thinking_value = _get_thinking_value(question_context)
    if thinking_value is None:
        return "not_forwarded"
    parameters["enable_thinking"] = thinking_value
    return "enabled" if thinking_value else "disabled"


def _apply_anthropic_thinking_settings(data: Dict[str, Any], max_tokens: int, question_context: OCSQuestionContext) -> tuple[int, str]:
    thinking_value = _get_thinking_value(question_context)
    if thinking_value is None:
        return max_tokens, "not_forwarded"
    if thinking_value is True:
        thinking_budget = _get_thinking_budget(question_context)
        request_max_tokens = max(max_tokens, thinking_budget + 1)
        data["max_tokens"] = request_max_tokens
        data["thinking"] = {
            "type": "enabled",
            "budget_tokens": min(thinking_budget, request_max_tokens - 1)
        }
        data["temperature"] = 1
        return request_max_tokens, "enabled"
    data["thinking"] = {
        "type": "disabled"
    }
    return max_tokens, "disabled"


def _describe_thinking_payload(provider: str, data: Dict[str, Any]) -> str:
    if provider == "openai_chat_completions":
        return str(data.get("reasoning_effort", "not_forwarded"))
    if provider == "openai_responses":
        reasoning = data.get("reasoning") or {}
        return str(reasoning.get("effort", "not_forwarded"))
    if provider == "dashscope":
        parameters = data.get("parameters") or {}
        return str(parameters.get("enable_thinking", "not_forwarded"))
    if provider == "anthropic":
        thinking = data.get("thinking") or {}
        return str(thinking.get("type", "not_forwarded"))
    return "unknown"


def _extract_request_max_tokens(provider: str, data: Dict[str, Any]) -> Optional[int]:
    if provider == "openai_chat_completions":
        return data.get("max_tokens")
    if provider == "openai_responses":
        return data.get("max_output_tokens")
    if provider == "dashscope":
        parameters = data.get("parameters") or {}
        return parameters.get("max_tokens")
    if provider == "anthropic":
        return data.get("max_tokens")
    return None


def _extract_text_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), str):
            return value["content"]
        return ""
    if isinstance(value, list):
        parts = [_extract_text_value(item) for item in value]
        return "".join(part for part in parts if part)
    return ""


def _extract_openai_chat_text(result: Dict[str, Any]) -> str:
    choices = result.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return _extract_text_value(message.get("content")).strip()


def _extract_openai_responses_text(result: Dict[str, Any]) -> str:
    output_text = result.get("output_text")
    if output_text:
        text = _extract_text_value(output_text).strip()
        if text:
            return text

    texts = []
    for item in result.get("output") or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content") or []:
            text = _extract_text_value(content)
            if text:
                texts.append(text)
    return "".join(texts).strip()


def _extract_dashscope_text(result: Dict[str, Any]) -> str:
    output = result.get("output") or {}
    choices = output.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        text = _extract_text_value(message.get("content")).strip()
        if text:
            return text
    return _extract_text_value(output.get("text")).strip()


def _extract_anthropic_text(result: Dict[str, Any]) -> str:
    texts = []
    for block in result.get("content") or []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            texts.append(block["text"])
    return "".join(texts).strip()


def _extract_response_text(provider: str, result: Dict[str, Any]) -> str:
    if provider == "openai_chat_completions":
        return _extract_openai_chat_text(result)
    if provider == "openai_responses":
        return _extract_openai_responses_text(result)
    if provider == "dashscope":
        return _extract_dashscope_text(result)
    if provider == "anthropic":
        return _extract_anthropic_text(result)
    return ""


def _strip_code_fences(text: str) -> str:
    cleaned = (text or "").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 3:
            return "\n".join(lines[1:-1]).strip()
    return cleaned


def _extract_answer_text(raw_text: str, structured_output: bool) -> str:
    cleaned_text = _strip_code_fences(raw_text)
    if not structured_output:
        return cleaned_text

    try:
        parsed = json.loads(cleaned_text)
        if isinstance(parsed, dict) and parsed.get("answer") is not None:
            return str(parsed["answer"]).strip()
    except json.JSONDecodeError:
        logger.warning("结构化输出解析失败，回退到原始文本")

    return cleaned_text


def _format_sse_event(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_stream_result_payload(
    question_context: OCSQuestionContext,
    answer: str,
    source: str,
    confidence: float,
    question_type: Optional[str] = None,
    success: Optional[bool] = None
) -> Dict[str, Any]:
    resolved_type = normalize_question_type(question_type or question_context.type) or (question_type or question_context.type or "")
    normalized_answer = normalize_answer_for_type(answer, resolved_type, question_context.options or "") if answer else ""
    is_success = bool(normalized_answer) if success is None else success
    return {
        "code": settings.RESPONSE_CODE_SUCCESS if is_success else settings.RESPONSE_CODE_ERROR,
        "question": question_context.title,
        "question_type": resolved_type,
        "options": question_context.options or "",
        "answer": normalized_answer,
        "source": source,
        "confidence": confidence
    }


def _extract_stream_chunk(provider: str, event_name: Optional[str], payload: Dict[str, Any]) -> str:
    event_type = payload.get("type") or event_name

    if provider == "openai_chat_completions":
        choices = payload.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        return _extract_text_value(delta.get("content"))

    if provider == "openai_responses":
        if event_type == "response.output_text.delta":
            return _extract_text_value(payload.get("delta"))
        return ""

    if provider == "dashscope":
        return _extract_dashscope_text(payload)

    if provider == "anthropic":
        if event_type != "content_block_delta":
            return ""
        delta = payload.get("delta") or {}
        if delta.get("type") == "text_delta":
            return delta.get("text", "")
        return ""

    return ""


async def _iter_streaming_chunks(response: aiohttp.ClientResponse, provider: str) -> AsyncIterator[str]:
    current_event = None

    while True:
        raw_line = await response.content.readline()
        if not raw_line:
            break

        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line:
            current_event = None
            continue

        if line.startswith("event:"):
            current_event = line[6:].strip()
            continue

        if not line.startswith("data:"):
            continue

        data_line = line[5:].strip()
        if not data_line:
            continue
        if data_line == "[DONE]":
            break

        try:
            payload = json.loads(data_line)
        except json.JSONDecodeError:
            continue

        chunk = _extract_stream_chunk(provider, current_event, payload)
        if chunk:
            yield chunk

        event_type = payload.get("type") or current_event
        if provider == "openai_responses" and event_type == "response.completed":
            break
        if provider == "anthropic" and event_type == "message_stop":
            break


async def _read_streaming_response(response: aiohttp.ClientResponse, provider: str) -> str:
    chunks = []
    async for chunk in _iter_streaming_chunks(response, provider):
        chunks.append(chunk)
    return "".join(chunks).strip()


def _build_structured_prompt(system_prompt: str) -> str:
    return (
        f"{system_prompt}\n"
        "请仅返回一个JSON对象，格式为{\"answer\":\"最终答案\"}。"
        "不要返回Markdown代码块，也不要添加额外解释。"
    )


def _build_ai_prompt(question_context: OCSQuestionContext) -> tuple[str, str, str, int]:
    q_type = normalize_question_type(question_context.type) or (question_context.type.lower() if question_context.type else "")
    max_tokens = _get_max_output_tokens()

    if q_type == "completion":
        system_prompt = "你是OCS网课助手AI答题系统。这是一道填空题，请直接回答填空处的内容，不要进行任何解释或讲解。不要返回选项字母，只返回填空的答案内容。"
        user_content = f"【填空题】问题：{question_context.title}"
        if question_context.options:
            user_content += f"\n参考选项：{question_context.options}"
    elif q_type == "single":
        system_prompt = "你是OCS网课助手AI答题系统。这是一道单选题，请仔细分析题目和选项，直接回答正确选项的字母（如A、B、C、D）。只返回选项字母，不要返回选项内容，不要有任何解释。"
        user_content = f"【单选题】问题：{question_context.title}\n选项：{question_context.options}" if question_context.options else f"【单选题】问题：{question_context.title}"
    elif q_type == "multiple":
        system_prompt = "你是OCS网课助手AI答题系统。这是一道多选题，请仔细分析题目和选项，直接回答所有正确选项的字母，用#号连接（如A#B#C）。只返回选项字母，不要返回选项内容，不要有任何解释。"
        user_content = f"【多选题】问题：{question_context.title}\n选项：{question_context.options}" if question_context.options else f"【多选题】问题：{question_context.title}"
    elif q_type == "judgment":
        system_prompt = "你是OCS网课助手AI答题系统。这是一道判断题，请直接回答'对'或'错'。只返回一个字，不要有任何解释。"
        user_content = f"【判断题】问题：{question_context.title}"
    else:
        system_prompt = "你是OCS网课助手AI答题系统。请根据题目类型回答问题。如果是填空题，只返回填空内容；如果是选择题，只返回选项字母；如果是判断题，只回答'对'或'错'。"
        user_content = f"问题：{question_context.title}"
        if question_context.options:
            user_content += f"\n选项：{question_context.options}"

    if _structured_output_enabled(question_context):
        system_prompt = _build_structured_prompt(system_prompt)

    return q_type, system_prompt, user_content, max_tokens


def _build_openai_chat_request(system_prompt: str, user_content: str, max_tokens: int, question_context: OCSQuestionContext) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
    }
    data = {
        "model": settings.AI_MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1
    }

    _apply_openai_chat_thinking_settings(data, question_context)
    if _structured_output_enabled(question_context):
        data["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "answer_response",
                "schema": _ANSWER_JSON_SCHEMA,
                "strict": True
            }
        }
    if _streaming_enabled(question_context):
        data["stream"] = True

    return _openai_chat_endpoint(settings.AI_MODEL_BASE_URL), headers, data


def _build_openai_responses_request(system_prompt: str, user_content: str, max_tokens: int, question_context: OCSQuestionContext) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
    }
    data = {
        "model": settings.AI_MODEL_NAME,
        "instructions": system_prompt,
        "input": user_content,
        "max_output_tokens": max_tokens,
        "temperature": 0.1
    }

    _apply_openai_responses_thinking_settings(data, question_context)
    if _structured_output_enabled(question_context):
        data["text"] = {
            "format": {
                "type": "json_schema",
                "name": "answer_response",
                "schema": _ANSWER_JSON_SCHEMA,
                "strict": True
            }
        }
    if _streaming_enabled(question_context):
        data["stream"] = True

    return _openai_responses_endpoint(settings.AI_MODEL_BASE_URL), headers, data


def _build_dashscope_request(system_prompt: str, user_content: str, max_tokens: int, question_context: OCSQuestionContext) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
    }
    data = {
        "model": settings.AI_MODEL_NAME,
        "input": {
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ]
        },
        "parameters": {
            "result_format": "message",
            "max_tokens": max_tokens
        }
    }

    _apply_dashscope_thinking_settings(data["parameters"], question_context)
    if _streaming_enabled(question_context):
        headers["X-DashScope-SSE"] = "enable"
        data["parameters"]["incremental_output"] = True

    return _dashscope_endpoint(settings.AI_MODEL_BASE_URL), headers, data


def _build_anthropic_request(system_prompt: str, user_content: str, max_tokens: int, question_context: OCSQuestionContext) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": settings.AI_MODEL_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    data = {
        "model": settings.AI_MODEL_NAME,
        "system": system_prompt,
        "messages": [
            {"role": "user", "content": user_content}
        ],
        "max_tokens": max_tokens
    }

    _apply_anthropic_thinking_settings(data, max_tokens, question_context)
    if _structured_output_enabled(question_context):
        data["output_config"] = {
            "format": {
                "type": "json_schema",
                "schema": _ANSWER_JSON_SCHEMA
            }
        }
    if _streaming_enabled(question_context):
        data["stream"] = True

    return _anthropic_endpoint(settings.AI_MODEL_BASE_URL), headers, data


def _build_provider_request(provider: str, system_prompt: str, user_content: str, max_tokens: int, question_context: OCSQuestionContext) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    if provider == "openai_chat_completions":
        return _build_openai_chat_request(system_prompt, user_content, max_tokens, question_context)
    if provider == "openai_responses":
        return _build_openai_responses_request(system_prompt, user_content, max_tokens, question_context)
    if provider == "dashscope":
        return _build_dashscope_request(system_prompt, user_content, max_tokens, question_context)
    if provider == "anthropic":
        return _build_anthropic_request(system_prompt, user_content, max_tokens, question_context)
    raise ValueError(f"不支持的AI接口类型: {provider}")


async def process_question_with_multi_layer(
    question_context: OCSQuestionContext,
    use_ai: bool = True,
    use_question_bank: bool = True,
    use_database: bool = False
) -> Optional[Dict[str, Any]]:
    """多层查询：手动题库 -> AI"""
    clean_title = clean_question_text(question_context.title)
    clean_options = clean_question_text(question_context.options) if question_context.options else ""

    normalized_input_type = normalize_question_type(question_context.type)
    detected_type = detect_question_type(clean_title, clean_options)
    final_type = normalized_input_type or detected_type
    if detected_type == "judgment" and normalized_input_type in ["", "single"]:
        final_type = "judgment"

    logger.info(f"题目类型检测: 原始类型={question_context.type}, 归一化类型={normalized_input_type}, 检测类型={detected_type}, 最终类型={final_type}")

    updated_context = OCSQuestionContext(
        title=clean_title,
        type=final_type,
        options=clean_options,
        thinking=question_context.thinking,
        thinking_budget=question_context.thinking_budget,
        structured_output=question_context.structured_output,
        stream=question_context.stream
    )

    query_functions = []

    # 优先查询手动题库
    if use_question_bank:
        query_functions.append(("manual", query_manual_question_bank))

    # 最后使用AI
    if use_ai:
        query_functions.append(("ai", query_ai))

    for source_name, query_func in query_functions:
        try:
            logger.info(f"尝试从{source_name}获取答案: 问题={updated_context.title[:50]}..., 类型={updated_context.type}")
            result = await query_func(updated_context)

            if result:
                # 如果手动题库返回了题型，优先使用返回的题型
                result_type = normalize_question_type(result.get('question_type') or updated_context.type) or updated_context.type
                result['question_type'] = result_type
                result['answer'] = normalize_answer_for_type(
                    result['answer'],
                    result_type,
                    updated_context.options or ""
                )
                logger.info(f"成功从{source_name}获取答案: 问题={updated_context.title[:50]}..., 题型={result_type}, 答案={result['answer']}")
                return result

        except asyncio.TimeoutError:
            logger.warning(f"{source_name}查询超时: {updated_context.title[:50]}...")
            continue
        except Exception as e:
            logger.error(f"{source_name}查询出错: {str(e)} - 问题: {updated_context.title[:50]}...")
            continue

    logger.warning(f"所有查询方式都失败: {updated_context.title[:50]}...")
    return None


async def query_ai_stream(question_context: OCSQuestionContext) -> AsyncIterator[str]:
    """使用AI流式查询答案，并输出统一 SSE 事件"""
    logger.info(f"使用AI流式查询答案: 类型={question_context.type}, 问题={question_context.title[:50]}...")

    try:
        provider = settings.ai_model_provider
        q_type, system_prompt, user_content, max_tokens = _build_ai_prompt(question_context)
        url, headers, data = _build_provider_request(provider, system_prompt, user_content, max_tokens, question_context)

        session = await get_http_session()
        async with session.post(
            url,
            headers=headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"AI流式请求失败: provider={provider}, 状态码={response.status}, 响应={error_text}")
                yield _format_sse_event(
                    "done",
                    _build_stream_result_payload(question_context, "", "none", 0.0, q_type, False)
                )
                return

            content_type = (response.headers.get("Content-Type") or "").lower()
            chunks = []

            if "text/event-stream" in content_type:
                async for chunk in _iter_streaming_chunks(response, provider):
                    chunks.append(chunk)
                    yield _format_sse_event("chunk", {"text": chunk})
                raw_text = "".join(chunks).strip()
            else:
                result = await response.json(content_type=None)
                raw_text = _extract_response_text(provider, result)

            answer = _extract_answer_text(raw_text, _structured_output_enabled(question_context)).strip()
            if not answer:
                logger.warning(f"AI流式返回空答案: provider={provider}, 问题={question_context.title[:50]}...")
                yield _format_sse_event(
                    "done",
                    _build_stream_result_payload(question_context, "", "none", 0.0, q_type, False)
                )
                return

            yield _format_sse_event(
                "done",
                _build_stream_result_payload(question_context, answer, "ai", 0.8, q_type, True)
            )
    except Exception as e:
        logger.error(f"AI流式查询出错: {e}")
        yield _format_sse_event(
            "done",
            _build_stream_result_payload(question_context, "", "none", 0.0, question_context.type, False)
        )


async def process_question_with_multi_layer_stream(
    question_context: OCSQuestionContext,
    use_ai: bool = True,
    use_question_bank: bool = True,
    use_database: bool = False
) -> AsyncIterator[str]:
    """多层流式查询：手动题库 -> AI SSE"""
    clean_title = clean_question_text(question_context.title)
    clean_options = clean_question_text(question_context.options) if question_context.options else ""

    normalized_input_type = normalize_question_type(question_context.type)
    detected_type = detect_question_type(clean_title, clean_options)
    final_type = normalized_input_type or detected_type
    if detected_type == "judgment" and normalized_input_type in ["", "single"]:
        final_type = "judgment"

    updated_context = OCSQuestionContext(
        title=clean_title,
        type=final_type,
        options=clean_options,
        thinking=question_context.thinking,
        thinking_budget=question_context.thinking_budget,
        structured_output=question_context.structured_output,
        stream=question_context.stream
    )

    if use_question_bank:
        try:
            logger.info(f"尝试从manual获取流式答案: 问题={updated_context.title[:50]}..., 类型={updated_context.type}")
            result = await query_manual_question_bank(updated_context)
            if result:
                result_type = normalize_question_type(result.get('question_type') or updated_context.type) or updated_context.type
                logger.info(f"成功从manual获取流式答案: 问题={updated_context.title[:50]}..., 题型={result_type}")
                yield _format_sse_event(
                    "done",
                    _build_stream_result_payload(
                        updated_context,
                        result.get('answer', ''),
                        "manual",
                        float(result.get('confidence', 1.0)),
                        result_type,
                        True
                    )
                )
                return
        except asyncio.TimeoutError:
            logger.warning(f"manual流式查询超时: {updated_context.title[:50]}...")
        except Exception as e:
            logger.error(f"manual流式查询出错: {str(e)} - 问题: {updated_context.title[:50]}...")

    if use_ai:
        async for event in query_ai_stream(updated_context):
            yield event
        return

    yield _format_sse_event(
        "done",
        _build_stream_result_payload(updated_context, "", "none", 0.0, updated_context.type, False)
    )


async def query_ai(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """使用AI查询答案"""
    logger.info(f"使用AI查询答案: 类型={question_context.type}, 问题={question_context.title[:50]}...")
    try:
        provider = settings.ai_model_provider
        q_type, system_prompt, user_content, max_tokens = _build_ai_prompt(question_context)
        url, headers, data = _build_provider_request(provider, system_prompt, user_content, max_tokens, question_context)
        use_stream = _streaming_enabled(question_context)

        thinking_value = _get_thinking_value(question_context)
        request_max_tokens = _extract_request_max_tokens(provider, data)
        thinking_payload = _describe_thinking_payload(provider, data)
        logger.info(
            f"AI请求: provider={provider}, 模型={settings.AI_MODEL_NAME}, 类型={q_type}, "
            f"thinking={thinking_value}, thinking_payload={thinking_payload}, "
            f"max_output_tokens={request_max_tokens}, "
            f"structured={_structured_output_enabled(question_context)}, stream={use_stream}"
        )

        session = await get_http_session()
        async with session.post(
            url,
            headers=headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"AI API请求失败: provider={provider}, 状态码={response.status}, 响应={error_text}")
                return None

            if use_stream:
                raw_text = await _read_streaming_response(response, provider)
            else:
                result = await response.json(content_type=None)
                raw_text = _extract_response_text(provider, result)

            answer = _extract_answer_text(raw_text, _structured_output_enabled(question_context)).strip()
            logger.info(f"AI返回的原始答案: provider={provider}, 类型={q_type}, 答案={answer}")

            if not answer:
                logger.warning(f"AI返回空答案: provider={provider}, 问题={question_context.title[:50]}...")
                return None

            return {
                "question": question_context.title,
                "question_type": q_type,
                "options": question_context.options or "",
                "answer": answer,
                "source": "ai",
                "confidence": 0.8,
                "metadata": {
                    "provider": provider,
                    "model": settings.AI_MODEL_NAME,
                    "question_type": q_type,
                    "thinking": thinking_value,
                    "structured_output": _structured_output_enabled(question_context),
                    "stream": use_stream
                }
            }
    except Exception as e:
        logger.error(f"AI查询出错: {e}")
        return None
