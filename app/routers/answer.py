"""
OCS网课助手答题API路由
"""
from fastapi import APIRouter, HTTPException
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


@router.post("/config/validate")
async def validate_ocs_config(config: str = None):
    """
    验证OCS题库配置格式
    """
    from app.utils.ocs_validator import validate_ocs_config
    
    # 如果没有提供配置，使用环境变量中的配置
    if not config:
        config = settings.QUESTION_BANK_CONFIG
    
    if not config:
        return {
            "valid": False,
            "error": "未提供配置，且环境变量中未配置QUESTION_BANK_CONFIG"
        }
    
    result = validate_ocs_config(config)
    return result


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


@router.post("/status")
async def refresh_question_bank_status():
    """
    刷新题库状态 - OCS刷新题库状态接口（POST方法）
    """
    # 调用GET方法获取状态
    return await get_question_bank_status()


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
        
        # 处理URL编码
        from urllib.parse import unquote
        if q:
            q = unquote(q)
        if options:
            options = unquote(options)
        
        # 构建OCS兼容的上下文
        question_context = OCSQuestionContext(
            title=q,
            type=type,
            options=options
        )
        
        logger.info(f"OCS搜索请求: {q}, 类型: {type}, 选项: {options}")
        
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
            logger.warning(f"OCS搜索未找到答案: {q}, 响应: {response_data}")
            return response_data
        
        logger.info(f"OCS搜索成功，来源: {result['source']}, 问题: {q}")
        
        # 处理答案格式，如果是选择题则提取选项字母
        answer_text = result['answer']
        answers = []
        
        # 如果是单选题或多选题，提取选项字母
        if type in ["single", "multiple"] and answer_text:
            # 简单处理：如果答案是单个字母，直接使用
            if len(answer_text) <= 5 and answer_text.replace("#", "").replace(" ", "").isalpha():
                answers = answer_text.split("#") if "#" in answer_text else [answer_text]
            else:
                # 否则使用完整答案
                answers = [answer_text]
        else:
            # 其他题型直接使用答案
            answers = [answer_text]
        
        # 构建标准响应格式
        response_data = {
            "code": settings.RESPONSE_CODE_SUCCESS,
            "results": [
                {
                    "question": q,
                    "answer": answers[0] if answers else ""
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