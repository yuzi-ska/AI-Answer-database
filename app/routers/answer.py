"""
OCS网课助手答题API路由
每次请求都实时查询，不使用缓存，不保存结果
"""
from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime
from app.schemas.answer import OCSQuestionContext
from app.core.config import settings
from app.utils.answer_processor import process_question_with_multi_layer, load_manual_question_bank, MANUAL_QUESTION_BANK_PATH
from app.utils.logger import logger
import json
import os

router = APIRouter()


@router.get("/health")
@router.head("/health")
async def api_health():
    """API健康检查"""
    return {"status": "ok", "api": "answer"}


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
                    "status": "available"
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


# ============ 手动题库管理接口 ============

@router.get("/manual-bank")
async def get_manual_question_bank():
    """
    获取手动题库内容
    """
    try:
        bank = load_manual_question_bank()
        return {
            "status": "ok",
            "count": len(bank),
            "question_bank": bank
        }
    except Exception as e:
        logger.error(f"获取手动题库失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取手动题库失败: {str(e)}")


@router.post("/manual-bank/add")
async def add_manual_question(question: str, answer: str):
    """
    添加题目到手动题库
    
    - question: 题目内容
    - answer: 答案
    """
    try:
        bank = load_manual_question_bank()
        
        # 添加新题目
        bank[question.strip()] = {
            "answer": answer.strip(),
            "added_at": str(datetime.now()) if 'datetime' in dir() else ""
        }
        
        # 保存到文件
        with open(MANUAL_QUESTION_BANK_PATH, 'w', encoding='utf-8') as f:
            json.dump(bank, f, ensure_ascii=False, indent=2)
        
        logger.info(f"手动题库已添加题目: {question[:50]}...")
        
        return {
            "status": "ok",
            "message": "添加成功",
            "count": len(bank)
        }
    except Exception as e:
        logger.error(f"添加手动题目失败: {e}")
        raise HTTPException(status_code=500, detail=f"添加失败: {str(e)}")


@router.delete("/manual-bank/remove")
async def remove_manual_question(question: str):
    """
    从手动题库删除题目
    
    - question: 要删除的题目内容
    """
    try:
        bank = load_manual_question_bank()
        
        if question.strip() not in bank:
            raise HTTPException(status_code=404, detail="题目不存在")
        
        del bank[question.strip()]
        
        # 保存到文件
        with open(MANUAL_QUESTION_BANK_PATH, 'w', encoding='utf-8') as f:
            json.dump(bank, f, ensure_ascii=False, indent=2)
        
        logger.info(f"手动题库已删除题目: {question[:50]}...")
        
        return {
            "status": "ok",
            "message": "删除成功",
            "count": len(bank)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除手动题目失败: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.delete("/manual-bank/clear")
async def clear_manual_question_bank():
    """
    清空手动题库
    """
    try:
        # 清空文件
        with open(MANUAL_QUESTION_BANK_PATH, 'w', encoding='utf-8') as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
        
        logger.info("手动题库已清空")
        
        return {
            "status": "ok",
            "message": "手动题库已清空"
        }
    except Exception as e:
        logger.error(f"清空手动题库失败: {e}")
        raise HTTPException(status_code=500, detail=f"清空失败: {str(e)}")


@router.get("/search")
@router.head("/search")
async def search_question(q: str = "", type: str = "single", options: str = ""):
    """
    OCS题库搜索接口 - 兼容OCS的搜索请求
    返回OCS标准格式：{code: 1, data: { answers: [3, 5], title: '1+2' }, msg: '成功'}
    
    每次请求都实时查询：
    1. 手动题库（最高优先级）
    2. OCS题库
    3. AI回答（兜底）
    """
    try:
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
        
        logger.info(f"OCS搜索请求: {clean_q}, 类型: {type}")
        
        # 使用多层查询架构获取答案（实时查询，不缓存）
        result = await process_question_with_multi_layer(
            question_context=question_context,
            use_ai=True,
            use_question_bank=True,
            use_database=False  # 不使用数据库
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
        
        logger.info(f"OCS搜索响应: {response_data}")
        
        return response_data
        
    except Exception as e:
        response_data = {
            "code": settings.RESPONSE_CODE_ERROR,
            "results": []
        }
        logger.error(f"OCS搜索出错: {str(e)}, 问题: {q}, 响应: {response_data}")
        return response_data
