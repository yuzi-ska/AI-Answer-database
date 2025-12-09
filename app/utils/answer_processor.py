"""
OCS网课助手答题处理器
支持SQL→题库→AI的查询顺序
"""
import asyncio
import aiohttp
import json
import logging
import hashlib
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from app.schemas.answer import OCSQuestionContext, AnswerResult
from app.core.config import settings
from app.utils.cache_manager import cache_manager
from app.utils.logger import logger
from app.models import SessionLocal, create_tables
from app.models.db_utils import get_question_answer_by_full_match, create_question_answer, normalize_options
from app.utils.question_detector import detect_question_type, clean_question_text, normalize_answer_for_type


from contextlib import contextmanager

@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def process_question_with_multi_layer(
    question_context: OCSQuestionContext,
    use_ai: bool = True,
    use_question_bank: bool = True,
    use_database: bool = True
) -> Optional[Dict[str, Any]]:
    """
    使用多层查询架构处理问题
    顺序: SQL查询 -> 题库查询 -> AI回答
    """
    # 清理题目文本
    clean_title = clean_question_text(question_context.title)
    clean_options = normalize_options(question_context.options or "")
    
    # 智能检测题目类型，避免类型识别错误
    detected_type = detect_question_type(clean_title, clean_options)
    
    # 如果传入的类型与检测出的类型不一致，使用检测出的类型
    final_type = question_context.type if question_context.type else detected_type
    
    logger.info(f"题目类型检测: 原始类型={question_context.type}, 检测类型={detected_type}, 最终类型={final_type}")
    
    # 更新问题上下文
    updated_context = OCSQuestionContext(
        title=clean_title,
        type=final_type,
        options=clean_options
    )
    
    # 使用更安全的哈希算法生成缓存键
    content = f"{updated_context.title}|{updated_context.type}|{updated_context.options or ''}"
    question_hash = f"answer_{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    # 首先检查缓存
    cached_result = await cache_manager.get(question_hash)
    if cached_result:
        logger.info(f"从缓存获取答案: {updated_context.title}, 类型: {updated_context.type}")
        return cached_result
    
    # 按优先级顺序尝试不同查询方式
    query_functions = []
    
    # 1. SQL查询（本地数据库）
    if use_database:
        query_functions.append(("database", query_database))
    
    # 2. 题库查询（如果配置了题库地址）
    if use_question_bank and settings.QUESTION_BANK_CONFIG:
        query_functions.append(("question_bank", query_question_bank))
    
    # 3. AI回答
    if use_ai:
        query_functions.append(("ai", query_ai))
    
    # 逐层查询
    for source_name, query_func in query_functions:
        try:
            logger.info(f"尝试从{source_name}获取答案: {updated_context.title}, 类型: {updated_context.type}")
            result = await query_func(updated_context)
            
            if result:
                # 标准化答案格式
                result['answer'] = normalize_answer_for_type(
                    result['answer'], 
                    updated_context.type, 
                    updated_context.options or ""
                )
                
                # 如果是AI回答，需要保存到数据库
                if source_name == "ai" and result.get('answer'):
                    try:
                        with get_db_session() as db:
                            create_question_answer(
                                db, 
                                updated_context.title, 
                                result['answer'], 
                                source="ai_generated",
                                question_type=updated_context.type,
                                options=updated_context.options
                            )
                            logger.info(f"AI生成的答案已保存到数据库: {updated_context.title}, 类型: {updated_context.type}, 答案: {result['answer'][:100]}...")
                    except Exception as e:
                        logger.error(f"保存AI答案到数据库失败: {e}")
                
                # 将结果存入缓存
                await cache_manager.set(
                    question_hash, 
                    result, 
                    ttl=settings.CACHE_TTL
                )
                logger.info(f"成功从{source_name}获取答案: {updated_context.title}, 类型: {updated_context.type}, 答案: {result['answer'][:100]}...")
                return result
                
        except asyncio.TimeoutError:
            logger.warning(f"{source_name}查询超时: {updated_context.title}")
            continue
        except Exception as e:
            logger.error(f"{source_name}查询出错: {str(e)} - 问题: {updated_context.title}")
            continue
    
    # 如果所有方式都失败，返回None
    logger.warning(f"所有查询方式都失败: {updated_context.title}")
    return None


async def query_database(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """
    查询本地数据库
    使用完全匹配（题目、类型和选项）
    """
    logger.info(f"查询本地数据库: {question_context.title}, 类型: {question_context.type}")
    try:
        with get_db_session() as db:
            # 标准化选项格式
            normalized_options = normalize_options(question_context.options or "")
            result = get_question_answer_by_full_match(
                db, 
                question_context.title,
                question_context.type,
                normalized_options
            )
            
            if result:
                logger.info(f"从数据库找到答案: {question_context.title}, 类型: {question_context.type}")
                return {
                    "question": question_context.title,
                    "question_type": result.question_type,
                    "options": result.options,
                    "answer": result.answer,
                    "source": "database",
                    "confidence": 1.0,  # 数据库查到的答案置信度最高
                    "metadata": {
                        "source": result.source,
                        "created_at": str(result.created_at) if hasattr(result, 'created_at') else None
                    }
                }
            else:
                logger.info(f"数据库中未找到完全匹配的答案: {question_context.title}, 类型: {question_context.type}")
                return None
    except Exception as e:
        logger.error(f"数据库查询出错: {e}, 问题: {question_context.title}")
        return None


async def query_question_bank(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """
    查询题库 - 支持OCS AnswererWrapper格式
    """
    logger.info(f"查询题库: {question_context.title}")
    try:
        # 解析OCS题库配置
        ocs_configs = parse_ocs_config(settings.QUESTION_BANK_CONFIG)
        
        if not ocs_configs:
            logger.warning(f"无效的OCS题库配置: {settings.QUESTION_BANK_CONFIG}")
            return None
        
        # 尝试每个配置
        for config in ocs_configs:
            try:
                result = await query_ocs_answerer(question_context, config)
                if result:
                    return result
            except Exception as e:
                logger.error(f"OCS配置查询出错: {e}, 配置: {config.get('name', 'unknown')}")
                continue
        
        # 所有配置都未找到答案
        logger.info(f"所有OCS题库配置都未找到答案: {question_context.title}")
        return None
        
    except Exception as e:
        logger.error(f"题库查询出错: {e}, 问题: {question_context.title}")
    
    return None


async def query_ocs_answerer(question_context: OCSQuestionContext, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    使用OCS AnswererWrapper配置查询题库
    """
    logger.info(f"使用OCS配置查询: {config.get('name', 'unknown')}, 问题: {question_context.title}")
    try:
        # 解析URL中的占位符
        url = config["url"]
        url = url.replace("${title}", question_context.title)
        url = url.replace("${type}", question_context.type)
        
        # 处理data参数
        data = config.get("data", {})
        resolved_data = {}
        for key, value in data.items():
            resolved_data[key] = value.replace("${title}", question_context.title).replace("${type}", question_context.type)
        
        # 设置请求头
        headers = config.get("headers", {})
        headers["Content-Type"] = "application/json"
        
        # 设置请求方法
        method = config.get("method", "get").lower()
        
        if method not in ["get", "post"]:
            logger.error(f"不支持的请求方法: {method}")
            return None
            
        async with aiohttp.ClientSession() as session:
            try:
                handler_result = None
                
                if method == "get":
                    # GET请求，将data参数添加到URL
                    if resolved_data:
                        query_params = "&".join([f"{k}={v}" for k, v in resolved_data.items()])
                        url += f"&{query_params}" if "?" in url else f"?{query_params}"
                    
                    async with session.get(
                        url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=settings.QUESTION_BANK_TIMEOUT)
                    ) as response:
                        handler_result = await handle_ocs_response(response, config)
                        
                elif method == "post":
                    # POST请求，将data参数作为请求体
                    async with session.post(
                        url,
                        json=resolved_data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=settings.QUESTION_BANK_TIMEOUT)
                    ) as response:
                        handler_result = await handle_ocs_response(response, config)
                
                if handler_result and len(handler_result) >= 2:
                    return {
                        "question": handler_result[0],
                        "answer": handler_result[1],
                        "source": "question_bank",
                        "confidence": 0.9,
                        "metadata": {
                            "source": config.get("name", "ocs"),
                            "config": config.get("name", "unknown"),
                            "question": handler_result[0]
                        }
                    }
                else:
                    return None
                
            except asyncio.TimeoutError:
                logger.warning(f"OCS配置查询超时: {config.get('name', 'unknown')}, 问题: {question_context.title}")
                return None  # 超时也返回None继续下一层查询
            except Exception as e:
                logger.error(f"OCS配置查询出错: {e}, 配置: {config.get('name', 'unknown')}")
                return None
                
    except Exception as e:
        logger.error(f"OCS配置查询出错: {e}, 配置: {config.get('name', 'unknown')}")
        return None


async def handle_ocs_response(response, config: Dict[str, Any]) -> Optional[List[str]]:
    """
    处理OCS响应并执行handler代码
    模拟OCS的handler执行方式
    """
    try:
        # 获取响应内容
        content_type = config.get("contentType", "json")
        
        if content_type == "json":
            response_text = await response.text()
            try:
                response_data = json.loads(response_text)
            except json.JSONDecodeError:
                logger.error(f"响应不是有效的JSON: {response_text[:100]}...")
                return None
        else:
            response_data = await response.text()
        
        # 执行handler代码
        handler_code = config.get("handler", "")
        if not handler_code:
            logger.error("未配置handler代码")
            return None
        
        # 创建安全的执行环境
        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "list": list,
                "dict": dict,
                "tuple": tuple,
                "join": "#".join,  # 用于多选题答案连接
            },
            "res": response_data,
            "undefined": None,
        }
        
        # 安全执行handler代码 - 仅支持预定义的handler类型
        handler_result = execute_handler_safely(handler_code, response_data)
        return handler_result
            
    except Exception as e:
        logger.error(f"执行OCS handler出错: {e}")
        return None


def parse_ocs_config(config_source: str) -> Optional[List[Dict[str, Any]]]:
    """
    解析OCS题库配置
    支持JSON字符串和订阅链接
    """
    if not config_source:
        return None
    
    # 如果是URL，尝试获取配置
    if config_source.startswith(("http://", "https://")):
        try:
            # 这里应该实现HTTP获取配置的逻辑
            # 为了安全，暂时不支持从URL获取配置
            logger.warning("不支持从URL获取OCS配置，请使用JSON字符串")
            return None
        except Exception as e:
            logger.error(f"获取OCS配置失败: {e}")
            return None
    
    # 解析JSON配置
    try:
        config_data = json.loads(config_source)
        
        # 确保是数组格式
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
    """
    使用AI查询答案
    """
    logger.info(f"使用AI查询答案: {question_context.title}")
    try:
        # 构建请求数据
        prompt = f"{settings.AI_AGENT_PROMPT}\n\n问题：{question_context.title}"
        if question_context.options:
            prompt += f"\n选项：{question_context.options}"
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.AI_MODEL_API_KEY}"
        }
        
        # 根据题目类型调整提示词
        if question_context.type == "completion":
            # 填空题专用提示词
            system_prompt = "你是OCS网课助手AI答题系统。这是一道填空题，请直接回答填空处的内容，不要进行任何解释或讲解。不要返回选项字母，只返回填空的答案内容。"
            
            user_content = f"【填空题】问题：{question_context.title}"
            
            data = {
                "model": settings.AI_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 100,
                "temperature": 0.1
            }
        elif question_context.options:
            # 有选项的选择题
            system_prompt = "你是OCS网课助手AI答题系统。这是一道选择题，请直接回答问题的正确选项，不要进行任何解释或讲解。如果是单选题，只回答选项字母（如A、B、C、D）。如果是多选题，用#连接选项字母（如A#B#C）。"
            
            user_content = f"【{question_context.type}】问题：{question_context.title}\n选项：{question_context.options}"
            
            data = {
                "model": settings.AI_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 50,
                "temperature": 0.1
            }
        else:
            # 其他题型或没有明确分类的情况
            system_prompt = "你是OCS网课助手AI答题系统。请根据题目类型回答问题。如果是填空题，只回答填空内容；如果是判断题，回答'对'或'错'；如果是问答题，提供简洁的答案。"
            
            user_content = f"问题：{question_context.title}"
            
            data = {
                "model": settings.AI_MODEL_NAME,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "max_tokens": 200,
                "temperature": 0.1
            }
        
        # 记录请求详情（不包含敏感信息）
        logger.info(f"AI请求: 模型={settings.AI_MODEL_NAME}, 基础URL={settings.AI_MODEL_BASE_URL}")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{settings.AI_MODEL_BASE_URL}/chat/completions",
                headers=headers,
                json=data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    
                    answer = result['choices'][0]['message']['content'].strip()
                    
                    logger.info(f"AI返回的原始答案: {answer}")
                    
                    return {
                        "question": question_context.title,
                        "answer": answer,
                        "source": "ai",
                        "confidence": 0.8,
                        "metadata": {
                            "model": settings.AI_MODEL_NAME,
                            "provider": settings.AI_MODEL_PROVIDER,
                            "base_url": settings.AI_MODEL_BASE_URL
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"AI API请求失败: {response.status}, {error_text}")
                    
                    # 尝试解析错误信息
                    try:
                        error_data = json.loads(error_text)
                        if "error" in error_data:
                            logger.error(f"AI API错误详情: {error_data['error']}")
                    except:
                        pass
                    
                    return None
    except Exception as e:
        logger.error(f"AI查询出错: {e}")
        return None


def execute_handler_safely(handler_code: str, response_data: Any) -> Optional[List[str]]:
    """
    安全执行handler代码
    仅支持预定义的handler类型，避免代码执行安全风险
    """
    try:
        # 预定义的安全handler映射
        SAFE_HANDLERS = {
            "default": lambda res: [res.get("question", ""), res.get("answer", "")] if isinstance(res, dict) else ["", str(res)],
            "ocs_standard": lambda res: [res.get("data", {}).get("title", ""), res.get("data", {}).get("answers", "")] if isinstance(res, dict) and res.get("code") == 1 else None,
            "array_response": lambda res: [res[0], res[1]] if isinstance(res, list) and len(res) >= 2 else None,
        }
        
        # 检查是否是预定义的handler
        if handler_code in SAFE_HANDLERS:
            return SAFE_HANDLERS[handler_code](response_data)
        
        # 尝试解析常见的响应格式
        if isinstance(response_data, dict):
            # 标准格式
            if "question" in response_data and "answer" in response_data:
                return [response_data["question"], response_data["answer"]]
            
            # OCS格式
            if "code" in response_data and "data" in response_data:
                data = response_data["data"]
                if "title" in data and ("answers" in data or "answer" in data):
                    answer = data.get("answers", data.get("answer", ""))
                    return [data["title"], answer]
        
        # 数组格式
        if isinstance(response_data, list) and len(response_data) >= 2:
            return [str(response_data[0]), str(response_data[1])]
        
        # 默认返回
        return ["", str(response_data)]
        
    except Exception as e:
        logger.error(f"安全执行handler出错: {e}")
        return None


def parse_answerer_response(response_text: str, handler_code: str) -> Optional[List[str]]:
    """
    解析Answerer响应，执行handler代码
    模拟OCS的handler执行方式
    """
    try:
        import json
        
        # 尝试解析JSON响应
        try:
            response_data = json.loads(response_text)
            if isinstance(response_data, list) and len(response_data) >= 2:
                return [response_data[0], response_data[1]]  # [question, answer]
        except json.JSONDecodeError:
            pass
        
        # 如果不是JSON，直接返回原始响应
        return ["", response_text]
    except Exception as e:
        logger.error(f"解析Answerer响应出错: {e}")
        return None