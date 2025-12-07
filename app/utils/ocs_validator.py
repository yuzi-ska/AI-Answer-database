"""
OCS题库配置验证和示例
"""
import json
from typing import Dict, Any, List


def validate_ocs_config(config: str) -> Dict[str, Any]:
    """
    验证OCS题库配置格式
    """
    try:
        # 解析JSON配置
        config_data = json.loads(config)
        
        # 确保是数组格式
        if isinstance(config_data, list):
            configs = config_data
        elif isinstance(config_data, dict):
            configs = [config_data]
        else:
            return {
                "valid": False,
                "error": "配置必须是JSON对象或数组"
            }
        
        # 验证每个配置
        for i, cfg in enumerate(configs):
            result = validate_single_config(cfg, i)
            if not result["valid"]:
                return result
        
        return {
            "valid": True,
            "count": len(configs),
            "configs": configs
        }
        
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "error": f"JSON解析错误: {str(e)}"
        }
    except Exception as e:
        return {
            "valid": False,
            "error": f"验证出错: {str(e)}"
        }


def validate_single_config(config: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    验证单个OCS配置
    """
    # 检查必需字段
    required_fields = ["url", "name", "handler"]
    for field in required_fields:
        if field not in config:
            return {
                "valid": False,
                "error": f"配置[{index}]缺少必需字段: {field}"
            }
    
    # 检查字段类型
    if not isinstance(config["url"], str):
        return {
            "valid": False,
            "error": f"配置[{index}]的url必须是字符串"
        }
    
    if not isinstance(config["name"], str):
        return {
            "valid": False,
            "error": f"配置[{index}]的name必须是字符串"
        }
    
    if not isinstance(config["handler"], str):
        return {
            "valid": False,
            "error": f"配置[{index}]的handler必须是字符串"
        }
    
    # 检查可选字段
    if "method" in config and config["method"] not in ["get", "post"]:
        return {
            "valid": False,
            "error": f"配置[{index}]的method必须是'get'或'post'"
        }
    
    if "contentType" in config and config["contentType"] not in ["json", "text"]:
        return {
            "valid": False,
            "error": f"配置[{index}]的contentType必须是'json'或'text'"
        }
    
    if "type" in config and config["type"] not in ["fetch", "GM_xmlhttpRequest"]:
        return {
            "valid": False,
            "error": f"配置[{index}]的type必须是'fetch'或'GM_xmlhttpRequest'"
        }
    
    return {
        "valid": True,
        "config": config
    }


def get_example_ocs_config() -> str:
    """
    获取OCS题库配置示例
    """
    example_config = [
        {
            "url": "https://example.com/api/search?question=${title}",
            "name": "示例题库",
            "homepage": "https://example.com",
            "method": "get",
            "contentType": "json",
            "type": "fetch",
            "headers": {
                "User-Agent": "OCS-API/1.0"
            },
            "handler": "return (res)=> res.code === 1 ? [res.question, res.answer] : undefined"
        }
    ]
    
    return json.dumps(example_config, indent=2, ensure_ascii=False)


def get_simple_ocs_config() -> str:
    """
    获取简单的OCS题库配置示例
    """
    simple_config = [
        {
            "url": "https://api.example.com/search?q=${title}",
            "name": "简单题库",
            "method": "get",
            "contentType": "json",
            "handler": "return (res)=> res.success ? [res.data.question, res.data.answer] : undefined"
        }
    ]
    
    return json.dumps(simple_config, indent=2, ensure_ascii=False)