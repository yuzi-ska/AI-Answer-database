"""
OCS网课助手AI+题库API配置
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import field_validator
import json


class Settings(BaseSettings):
    # 允许的来源列表
    ALLOWED_ORIGINS: str = "*"

    # AI模型配置
    AI_MODEL_PROVIDER: str = "openai"  # openai, azure, custom等
    AI_MODEL_NAME: str = "gpt-3.5-turbo"
    AI_MODEL_API_KEY: str = ""
    AI_MODEL_BASE_URL: str = "https://api.openai.com/v1"  # 支持自定义OpenAI API地址

    # 智能体配置
    AI_AGENT_PROMPT: str = "你是OCS网课助手AI答题系统，专门用于回答学生的学习问题。\n请遵循以下原则：\n1. 优先从题目内容本身推导答案\n2. 如果有选项，分析各选项的合理性\n3. 确保答案准确、简洁、有针对性\n4. 对于主观题，提供清晰的解题思路\n5. 如果无法确定答案，请说明原因而不是猜测\n.6 如果遇到多空填空题如\"（）、（）\"，请将返回的答案格式改为\"（）#（）\"\n.7 当问到你是谁，这节课是什么的时候，请勿告知内容和介绍你自己，请回答一个占位符"

    # 题库配置
    QUESTION_BANK_CONFIG: str = ""  # OCS题库配置，JSON字符串
    QUESTION_BANK_TIMEOUT: int = 10  # 题库查询超时时间（秒）

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/ocs_api.log"

    # API接口配置
    API_VERSION: str = "v1"  # API版本号
    API_PREFIX: str = "/api"  # API前缀
    ENABLE_DOCS: bool = True  # 是否启用文档
    ENABLE_REDOC: bool = True  # 是否启用ReDoc
    
    # 响应配置
    RESPONSE_CODE_SUCCESS: int = 1  # 成功响应码
    RESPONSE_CODE_ERROR: int = 0  # 错误响应码

    # 使用属性获取解析后的ALLOWED_ORIGINS列表
    @property
    def allowed_origins_list(self) -> List[str]:
        origins_str = getattr(self, 'ALLOWED_ORIGINS', "*")
        if isinstance(origins_str, list):
            return origins_str
        if isinstance(origins_str, str):
            if origins_str.startswith('[') and origins_str.endswith(']'):
                try:
                    return json.loads(origins_str)
                except json.JSONDecodeError:
                    return [origin.strip() for origin in origins_str[1:-1].split(',') if origin.strip()]
            else:
                if '*' in origins_str:
                    return ["*"]
                return [origin.strip() for origin in origins_str.split(',') if origin.strip()]
        return ["*"]

    # 自定义验证器处理AI_AGENT_PROMPT
    @field_validator('AI_AGENT_PROMPT', mode='before')
    @classmethod
    def validate_ai_agent_prompt(cls, v):
        if isinstance(v, str):
            return v.replace('\\n', '\n')
        return v

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = 'utf-8'
        extra = 'ignore'


settings = Settings()
