"""
OCS网课助手答题API路由
每次请求都实时查询，不使用缓存，不保存结果
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.schemas.answer import OCSQuestionContext
from app.utils.answer_processor import process_question_with_multi_layer, process_question_with_multi_layer_stream
from app.utils.logger import log_exception, logger
from app.utils.question_detector import clean_question_text, normalize_answer_for_type, normalize_question_type

router = APIRouter()


def _validate_advanced_request_options(thinking_budget: Optional[int]):
    if thinking_budget is not None and thinking_budget < 1:
        raise HTTPException(status_code=400, detail="thinking_budget 必须大于 0")


def _build_streaming_response(question_context: OCSQuestionContext) -> StreamingResponse:
    return StreamingResponse(
        process_question_with_multi_layer_stream(
            question_context=question_context,
            use_ai=True,
            use_question_bank=True,
            use_database=False
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/health")
@router.head("/health")
async def api_health():
    """API健康检查"""
    return {"status": "ok", "api": "answer"}


@router.get("/search")
@router.head("/search")
async def search_question(
    q: str = "",
    type: str = "",
    options: str = "",
    thinking: Optional[bool] = None,
    thinking_budget: Optional[int] = None,
    structured_output: bool = False,
    stream: bool = False
):
    """
    OCS题库搜索接口 - 兼容OCS的搜索请求
    返回OCS标准格式

    每次请求都实时查询：
    1. 手动题库（最高优先级）
    2. AI回答（兜底）
    """
    try:
        from urllib.parse import unquote

        if len(q) > 1000:
            raise HTTPException(status_code=400, detail="问题长度不能超过1000字符")
        if len(options) > 2000:
            raise HTTPException(status_code=400, detail="选项长度不能超过2000字符")

        if q:
            q = unquote(q)
        if type:
            type = unquote(type)
        if options:
            options = unquote(options)

        normalized_type = normalize_question_type(type) if type else ""
        if type and normalized_type not in ["single", "multiple", "completion", "judgment"]:
            raise HTTPException(status_code=400, detail="无效的题目类型")

        _validate_advanced_request_options(thinking_budget)

        clean_q = clean_question_text(q)
        clean_options = clean_question_text(options) if options else ""

        question_context = OCSQuestionContext(
            title=clean_q,
            type=normalized_type,
            options=clean_options,
            thinking=thinking,
            thinking_budget=thinking_budget,
            structured_output=structured_output,
            stream=stream
        )

        logger.info(
            f"OCS搜索请求: {clean_q[:50]}..., 类型: {type} -> {normalized_type}, "
            f"thinking={thinking}, thinking_budget={thinking_budget}, "
            f"structured_output={structured_output}, stream={stream}"
        )

        if stream and settings.AI_ENABLE_STREAMING_PARAMS:
            return _build_streaming_response(question_context)

        result = await process_question_with_multi_layer(
            question_context=question_context,
            use_ai=True,
            use_question_bank=True,
            use_database=False
        )

        if result is None:
            response_data = {
                "code": settings.RESPONSE_CODE_ERROR,
                "results": []
            }
            logger.warning(f"OCS搜索未找到答案: {clean_q[:50]}...")
            return response_data

        logger.info(f"OCS搜索成功，来源: {result['source']}, 问题: {clean_q[:50]}...")

        actual_type = normalize_question_type(result.get('question_type')) or normalized_type
        actual_options = result.get('options', clean_options)
        final_answer = normalize_answer_for_type(
            result['answer'],
            actual_type,
            actual_options
        )

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
        log_exception(f"OCS搜索出错，问题: {q[:50] if q else 'empty'}...", e)
        return response_data
