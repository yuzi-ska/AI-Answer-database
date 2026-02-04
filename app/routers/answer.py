"""
OCS网课助手答题API路由
每次请求都实时查询，不使用缓存，不保存结果
"""
from fastapi import APIRouter, HTTPException
from app.schemas.answer import OCSQuestionContext
from app.core.config import settings
from app.utils.answer_processor import process_question_with_multi_layer
from app.utils.logger import logger

router = APIRouter()


@router.get("/health")
@router.head("/health")
async def api_health():
    """API健康检查"""
    return {"status": "ok", "api": "answer"}


@router.get("/search")
@router.head("/search")
async def search_question(q: str = "", type: str = "single", options: str = ""):
    """
    OCS题库搜索接口 - 兼容OCS的搜索请求
    返回OCS标准格式

    每次请求都实时查询：
    1. 手动题库（最高优先级）
    2. AI回答（兜底）
    """
    try:
        from app.schemas.answer import OCSQuestionContext
        from app.utils.question_detector import clean_question_text, normalize_answer_for_type

        # 输入验证
        if len(q) > 1000:
            raise HTTPException(status_code=400, detail="问题长度不能超过1000字符")
        if len(options) > 2000:
            raise HTTPException(status_code=400, detail="选项长度不能超过2000字符")
        if type not in ["single", "multiple", "completion", "judgment"]:
            raise HTTPException(status_code=400, detail="无效的题目类型")

        # 处理URL编码
        from urllib.parse import unquote
        if q:
            q = unquote(q)
        if options:
            options = unquote(options)

        # 清理题目文本
        clean_q = clean_question_text(q)
        clean_options = clean_question_text(options) if options else ""

        # 构建OCS兼容的上下文
        question_context = OCSQuestionContext(
            title=clean_q,
            type=type,
            options=clean_options
        )

        logger.info(f"OCS搜索请求: {clean_q[:50]}..., 类型: {type}")

        # 使用多层查询架构获取答案（实时查询，不缓存）
        result = await process_question_with_multi_layer(
            question_context=question_context,
            use_ai=True,
            use_question_bank=False,  # 不使用OCS题库转发
            use_database=False  # 不使用数据库
        )

        if result is None:
            response_data = {
                "code": settings.RESPONSE_CODE_ERROR,
                "results": []
            }
            logger.warning(f"OCS搜索未找到答案: {clean_q[:50]}...")
            return response_data

        logger.info(f"OCS搜索成功，来源: {result['source']}, 问题: {clean_q[:50]}...")

        # 获取实际的题目类型（可能经过智能检测修正）
        actual_type = result.get('question_type', type)
        actual_options = result.get('options', clean_options)

        # 根据实际题型格式化答案
        final_answer = normalize_answer_for_type(
            result['answer'],
            actual_type,
            actual_options
        )

        # 构建标准响应格式
        response_data = {
            "code": settings.RESPONSE_CODE_SUCCESS,
            "results": [
                {
                    "question": clean_q,
                    "question_type": actual_type,
                    "options": actual_options,
                    "answer": final_answer
                }
            ]
        }

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        response_data = {
            "code": settings.RESPONSE_CODE_ERROR,
            "results": []
        }
        logger.error(f"OCS搜索出错: {str(e)}, 问题: {q[:50] if q else 'empty'}...")
        return response_data
