"""
OCS网课助手答题处理器
支持手动题库→题库→AI的查询顺序（不保存结果到数据库/缓存）
每次请求都实时查询，不使用缓存
"""
import asyncio
import aiohttp
import json
import os
from typing import Optional, Dict, Any, List
from app.schemas.answer import OCSQuestionContext, AnswerResult
from app.core.config import settings
from app.utils.logger import logger
from app.utils.question_detector import detect_question_type, clean_question_text, normalize_answer_for_type


# 手动题库文件路径
MANUAL_QUESTION_BANK_PATH = "manual_question_bank.json"


def load_manual_question_bank() -> Dict[str, Dict[str, str]]:
    """加载手动题库"""
    try:
        if os.path.exists(MANUAL_QUESTION_BANK_PATH):
            with open(MANUAL_QUESTION_BANK_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
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


async def process_question_with_multi_layer(
    question_context: OCSQuestionContext,
    use_ai: bool = True,
    use_question_bank: bool = True,
    use_database: bool = True
) -> Optional[Dict[str, Any]]:
    """多层查询：手动题库 -> 题库 -> AI"""
    clean_title = clean_question_text(question_context.title)
    clean_options = normalize_options(question_context.options or "") if question_context.options else ""
    
    detected_type = detect_question_type(clean_title, clean_options)
    final_type = question_context.type if question_context.type else detected_type
    
    logger.info(f"题目类型检测: 原始类型={question_context.type}, 检测类型={detected_type}, 最终类型={final_type}")
    
    updated_context = OCSQuestionContext(
        title=clean_title,
        type=final_type,
        options=clean_options
    )
    
    query_functions = []
    query_functions.append(("manual", query_manual_question_bank))
    
    if use_question_bank and settings.QUESTION_BANK_CONFIG:
        query_functions.append(("question_bank", query_question_bank))
    
    if use_ai:
        query_functions.append(("ai", query_ai))
    
    for source_name, query_func in query_functions:
        try:
            logger.info(f"尝试从{source_name}获取答案: 问题={updated_context.title}, 类型={updated_context.type}")
            result = await query_func(updated_context)
            
            if result:
                # 如果手动题库返回了题型，优先使用返回的题型
                result_type = result.get('question_type') or updated_context.type
                result['answer'] = normalize_answer_for_type(
                    result['answer'],
                    result_type,
                    updated_context.options or ""
                )
                logger.info(f"成功从{source_name}获取答案: 问题={updated_context.title}, 题型={result_type}, 答案={result['answer']}")
                return result
                
        except asyncio.TimeoutError:
            logger.warning(f"{source_name}查询超时: {updated_context.title}")
            continue
        except Exception as e:
            logger.error(f"{source_name}查询出错: {str(e)} - 问题: {updated_context.title}")
            continue
    
    logger.warning(f"所有查询方式都失败: {updated_context.title}")
    return None


async def query_question_bank(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """查询题库"""
    logger.info(f"查询题库: {question_context.title}")
    try:
        ocs_configs = parse_ocs_config(settings.QUESTION_BANK_CONFIG)
        
        if not ocs_configs:
            logger.warning("无效的OCS题库配置")
            return None
        
        for config in ocs_configs:
            try:
                result = await query_ocs_answerer(question_context, config)
                if result:
                    return result
            except Exception as e:
                logger.error(f"OCS配置查询出错: {e}, 配置: {config.get('name', 'unknown')}")
                continue
        
        logger.info(f"所有OCS题库配置都未找到答案: {question_context.title}")
        return None
        
    except Exception as e:
        logger.error(f"题库查询出错: {e}, 问题: {question_context.title}")
        return None


async def query_ocs_answerer(question_context: OCSQuestionContext, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """使用OCS AnswererWrapper配置查询题库"""
    logger.info(f"使用OCS配置查询: {config.get('name', 'unknown')}, 问题: {question_context.title}")
    try:
        url = config["url"]
        url = url.replace("${title}", question_context.title)
        url = url.replace("${type}", question_context.type)
        
        data = config.get("data", {})
        resolved_data = {}
        for key, value in data.items():
            resolved_data[key] = value.replace("${title}", question_context.title).replace("${type}", question_context.type)
        
        headers = config.get("headers", {})
        headers["Content-Type"] = "application/json"
        
        method = config.get("method", "get").lower()
        
        if method not in ["get", "post"]:
            logger.error(f"不支持的请求方法: {method}")
            return None
            
        async with aiohttp.ClientSession() as session:
            try:
                if method == "get":
                    if resolved_data:
                        query_params = "&".join([f"{k}={v}" for k, v in resolved_data.items()])
                        url += f"&{query_params}" if "?" in url else f"?{query_params}"
                    
                    async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=settings.QUESTION_BANK_TIMEOUT)) as response:
                        handler_result = await handle_ocs_response(response, config)
                        
                elif method == "post":
                    async with session.post(url, json=resolved_data, headers=headers, timeout=aiohttp.ClientTimeout(total=settings.QUESTION_BANK_TIMEOUT)) as response:
                        handler_result = await handle_ocs_response(response, config)
                
                if handler_result and len(handler_result) >= 2:
                    return {
                        "question": handler_result[0],
                        "answer": handler_result[1],
                        "source": "question_bank",
                        "confidence": 0.9,
                        "metadata": {"source": config.get("name", "ocs")}
                    }
                return None
                
            except asyncio.TimeoutError:
                logger.warning(f"OCS配置查询超时: {config.get('name', 'unknown')}")
                return None
            except Exception as e:
                logger.error(f"OCS配置查询出错: {e}")
                return None
                
    except Exception as e:
        logger.error(f"OCS配置查询出错: {e}")
        return None


async def handle_ocs_response(response, config: Dict[str, Any]) -> Optional[List[str]]:
    """处理OCS响应"""
    try:
        content_type = config.get("contentType", "json")
        
        if content_type == "json":
            response_text = await response.text()
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"响应不是有效的JSON: {response_text}")
                return None
        else:
            response_data = await response.text()
        
        handler_code = config.get("handler", "")
        if not handler_code:
            logger.error("未配置handler代码")
            return None
        
        handler_result = execute_handler_safely(handler_code, response_data)
        return handler_result
            
    except Exception as e:
        logger.error(f"执行OCS handler出错: {e}")
        return None


def parse_ocs_config(config_source: str) -> Optional[List[Dict[str, Any]]]:
    """解析OCS题库配置"""
    if not config_source:
        return None
    
    if config_source.startswith(("http://", "https://")):
        logger.warning("不支持从URL获取OCS配置，请使用JSON字符串")
        return None
    
    try:
        config_data = json.loads(config_source)
        if isinstance(config_data, list):
            return config_data
        elif isinstance(config_data, dict):
            return [config_data]
        else:
            logger.error(f"无效的OCS配置格式: {type(config_data)}")
            return None
    except json.JSONDecodeError as e:
        logger.error(f"解析OCS配置JSON失败: {e}")
        return None
    except Exception as e:
        logger.error(f"解析OCS配置出错: {e}")
        return None


async def query_ai(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """使用AI查询答案"""
    logger.info(f"使用AI查询答案: 类型={question_context.type}, 问题={question_context.title}")
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
        }
        
        # 根据题目类型配置提示词
        q_type = question_context.type.lower() if question_context.type else ""
        
        if q_type == "completion":
            # 填空题
            system_prompt = "你是OCS网课助手AI答题系统。这是一道填空题，请直接回答填空处的内容，不要进行任何解释或讲解。不要返回选项字母，只返回填空的答案内容。"
            user_content = f"【填空题】问题：{question_context.title}"
            if question_context.options:
                user_content += f"\n参考选项：{question_context.options}"
            max_tokens = 100
        elif q_type == "single":
            # 单选题
            system_prompt = "你是OCS网课助手AI答题系统。这是一道单选题，请仔细分析题目和选项，直接回答正确选项的字母（如A、B、C、D）。只返回选项字母，不要返回选项内容，不要有任何解释。"
            user_content = f"【单选题】问题：{question_context.title}\n选项：{question_context.options}" if question_context.options else f"【单选题】问题：{question_context.title}"
            max_tokens = 20
        elif q_type == "multiple":
            # 多选题
            system_prompt = "你是OCS网课助手AI答题系统。这是一道多选题，请仔细分析题目和选项，直接回答所有正确选项的字母，用#号连接（如A#B#C）。只返回选项字母，不要返回选项内容，不要有任何解释。"
            user_content = f"【多选题】问题：{question_context.title}\n选项：{question_context.options}" if question_context.options else f"【多选题】问题：{question_context.title}"
            max_tokens = 50
        elif q_type == "judgment":
            # 判断题
            system_prompt = "你是OCS网课助手AI答题系统。这是一道判断题，请直接回答'对'或'错'。只返回一个字，不要有任何解释。"
            user_content = f"【判断题】问题：{question_context.title}"
            max_tokens = 10
        else:
            # 默认处理
            system_prompt = "你是OCS网课助手AI答题系统。请根据题目类型回答问题。如果是填空题，只返回填空内容；如果是选择题，只返回选项字母；如果是判断题，只回答'对'或'错'。"
            user_content = f"问题：{question_context.title}"
            if question_context.options:
                user_content += f"\n选项：{question_context.options}"
            max_tokens = 100
        
        data = {
            "model": settings.AI_MODEL_NAME,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }
        
        logger.info(f"AI请求: 模型={settings.AI_MODEL_NAME}, 类型={q_type}, max_tokens={max_tokens}")
        logger.info(f"AI请求内容: {user_content}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{settings.AI_MODEL_BASE_URL}/chat/completions", headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 200:
                    result = await response.json()
                    answer = result['choices'][0]['message']['content'].strip()
                    logger.info(f"AI返回的原始答案: 类型={q_type}, 答案={answer}")
                    
                    return {
                        "question": question_context.title,
                        "answer": answer,
                        "source": "ai",
                        "confidence": 0.8,
                        "metadata": {"model": settings.AI_MODEL_NAME, "question_type": q_type}
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"AI API请求失败: 状态码={response.status}, 响应={error_text}")
                    return None
    except Exception as e:
        logger.error(f"AI查询出错: {e}")
        return None


def execute_handler_safely(handler_code: str, response_data: Any) -> Optional[List[str]]:
    """安全执行handler代码"""
    try:
        SAFE_HANDLERS = {
            "default": lambda res: [res.get("question", ""), res.get("answer", "")] if isinstance(res, dict) else ["", str(res)],
            "ocs_standard": lambda res: [res.get("data", {}).get("title", ""), res.get("data", {}).get("answers", "")] if isinstance(res, dict) and res.get("code") == 1 else None,
            "array_response": lambda res: [res[0], res[1]] if isinstance(res, list) and len(res) >= 2 else None,
        }
        
        if handler_code in SAFE_HANDLERS:
            return SAFE_HANDLERS[handler_code](response_data)
        
        if isinstance(response_data, dict):
            if "question" in response_data and "answer" in response_data:
                return [response_data["question"], response_data["answer"]]
            if "code" in response_data and "data" in response_data:
                data = response_data["data"]
                if "title" in data and ("answers" in data or "answer" in data):
                    answer = data.get("answers", data.get("answer", ""))
                    return [data["title"], answer]
        
        if isinstance(response_data, list) and len(response_data) >= 2:
            return [str(response_data[0]), str(response_data[1])]
        
        return ["", str(response_data)]
        
    except Exception as e:
        logger.error(f"安全执行handler出错: {e}")
        return None


def parse_answerer_response(response_text: str, handler_code: str) -> Optional[List[str]]:
    """解析Answerer响应"""
    try:
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, list) and len(response_data) >= 2:
                return [response_data[0], response_data[1]]
        except json.JSONDecodeError:
            pass
        
        return ["", response_text]
    except Exception as e:
        logger.error(f"解析Answerer响应出错: {e}")
        return None


def normalize_options(options: str) -> str:
    """标准化选项格式"""
    if not options:
        return ""
    lines = [line.strip() for line in options.split("\n") if line.strip()]
    return "\n".join(lines)
