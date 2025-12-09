"""
OCS网课助手答题API路由
"""
from fastapi import APIRouter
from typing import Optional
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

@router.get("/cache/clear")
async def clear_cache():
    """清空缓存"""
    from app.utils.cache_manager import cache_manager
    await cache_manager.clear()
    logger.info("缓存已清空")
    return {"status": "ok", "message": "缓存已清空"}





@router.get("/config/example")
async def get_config_example():
    """
    获取OCS题库配置示例
    """
    from app.utils.ocs_validator import get_example_ocs_config
    
    example = get_example_ocs_config()
    return {
        "status": "ok",
        "example": example
    }


@router.get("/config/simple")
async def get_simple_config_example():
    """
    获取简单的OCS题库配置示例
    """
    from app.utils.ocs_validator import get_simple_ocs_config
    
    example = get_simple_ocs_config()
    return {
        "status": "ok",
        "example": example
    }


@router.get("/status")
@router.head("/status")
async def get_question_bank_status():
    """
    获取题库状态 - OCS刷新题库状态接口
    """
    from app.utils.answer_processor import parse_ocs_config
    from app.core.config import settings
    
    try:
        # 检查是否配置了题库
        if not settings.QUESTION_BANK_CONFIG:
            return {
                "status": "error",
                "message": "未配置题库",
                "configured": False
            }
        
        # 解析配置
        configs = parse_ocs_config(settings.QUESTION_BANK_CONFIG)
        
        if not configs:
            return {
                "status": "error", 
                "message": "题库配置格式错误",
                "configured": False
            }
        
        # 返回题库状态信息
        return {
            "status": "ok",
            "message": "题库配置正常",
            "configured": True,
            "count": len(configs),
            "question_banks": [
                {
                    "name": config.get("name", "未知"),
                    "url": config.get("url", ""),
                    "method": config.get("method", "get"),
                    "status": "available"  # 简单状态检查
                }
                for config in configs
            ]
        }
        
    except Exception as e:
        logger.error(f"获取题库状态出错: {e}")
        return {
            "status": "error",
            "message": f"获取题库状态失败: {str(e)}",
            "configured": False
        }





@router.get("/search")
@router.head("/search")
async def search_question(q: str = "", type: str = "single", options: str = ""):
    """
    OCS题库搜索接口 - 兼容OCS的搜索请求
    返回OCS标准格式：{code: 1, data: { answers: [3, 5], title: '1+2' }, msg: '成功'}
    """
    try:
        from app.utils.answer_processor import process_question_with_multi_layer
        from app.schemas.answer import OCSQuestionContext
        from app.utils.question_detector import clean_question_text, normalize_answer_for_type
        
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
        
        logger.info(f"OCS搜索请求: {clean_q}, 原始类型: {type}, 选项: {clean_options}")
        
        # 使用多层查询架构获取答案
        result = await process_question_with_multi_layer(
            question_context=question_context,
            use_ai=True,
            use_question_bank=True,
            use_database=True
        )
        
        if result is None:
            response_data = {
                "code": settings.RESPONSE_CODE_ERROR,
                "results": []
            }
            logger.warning(f"OCS搜索未找到答案: {clean_q}, 响应: {response_data}")
            return response_data
        
        logger.info(f"OCS搜索成功，来源: {result['source']}, 问题: {clean_q}")
        
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
        
        # 打印完整的响应格式到日志
        logger.info(f"OCS搜索响应: {response_data}")
        
        return response_data
        
    except Exception as e:
        response_data = {
            "code": settings.RESPONSE_CODE_ERROR,
            "results": []
        }
        logger.error(f"OCS搜索出错: {str(e)}, 问题: {q}, 响应: {response_data}")
        return response_data