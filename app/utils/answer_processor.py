"""
OCS网课助手答题处理器
支持手动题库→AI的查询顺序（不保存结果到数据库/缓存）
每次请求都实时查询，不使用缓存
"""
import asyncio
import aiohttp
import json
import os
from typing import Optional, Dict, Any
from app.schemas.answer import OCSQuestionContext
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
    use_database: bool = False
) -> Optional[Dict[str, Any]]:
    """多层查询：手动题库 -> AI"""
    clean_title = clean_question_text(question_context.title)
    clean_options = question_context.options or ""

    detected_type = detect_question_type(clean_title, clean_options)
    final_type = question_context.type if question_context.type else detected_type

    logger.info(f"题目类型检测: 原始类型={question_context.type}, 检测类型={detected_type}, 最终类型={final_type}")

    updated_context = OCSQuestionContext(
        title=clean_title,
        type=final_type,
        options=clean_options
    )

    query_functions = []

    # 优先查询手动题库
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
                result_type = result.get('question_type') or updated_context.type
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


async def query_ai(question_context: OCSQuestionContext) -> Optional[Dict[str, Any]]:
    """使用AI查询答案"""
    logger.info(f"使用AI查询答案: 类型={question_context.type}, 问题={question_context.title[:50]}...")
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
