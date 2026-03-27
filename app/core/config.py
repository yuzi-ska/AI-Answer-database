"""
OCS网课助手AI答题API配置
"""
import json
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


AI_PROVIDER_ALIASES = {
    "openai": "openai_chat_completions",
    "openai_chat": "openai_chat_completions",
    "openai_chat_completions": "openai_chat_completions",
    "openai_responses": "openai_responses",
    "dashscope": "dashscope",
    "anthropic": "anthropic",
    "claude": "anthropic",
}


class Settings(BaseSettings):
    # 允许的来源列表
    ALLOWED_ORIGINS: str = "*"

    # AI模型配置
    AI_MODEL_PROVIDER: str = "openai_chat_completions"  # openai_chat_completions、openai_responses、dashscope、anthropic
    AI_MODEL_NAME: str = "gpt-3.5-turbo"
    AI_MODEL_API_KEY: str = ""
    AI_MODEL_BASE_URL: str = "https://api.openai.com/v1"  # 不同接口类型使用各自基础地址
    AI_ENABLE_THINKING_PARAMS: Optional[bool] = None  # None=不转发；true/false=默认向上游显式传递思考开启/关闭
    AI_ENABLE_STRUCTURED_OUTPUT_PARAMS: bool = False  # 允许向上游转发结构化输出参数
    AI_ENABLE_STREAMING_PARAMS: bool = False  # 允许向上游转发流式参数并启用 SSE 返回

    # 智能体配置
    AI_AGENT_PROMPT: str = "你是OCS网课助手AI答题系统，专门用于回答学生的学习问题。\n请遵循以下原则：\n1. 优先从题目内容本身推导答案\n2. 如果有选项，分析各选项的合理性\n3. 确保答案准确、简洁、有针对性\n4. 对于主观题，提供清晰的解题思路\n5. 如果无法确定答案，请说明原因而不是猜测\n.6 如果遇到多空填空题如\"（）、（）\"，请将返回的答案格式改为\"（）#（）\"\n.7 当问到你是谁，这节课是什么的时候，请勿告知内容和介绍你自己，请回答一个占位符"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE_PATH: str = "logs/ocs_api.log"

    # API接口配置
    API_VERSION: str = "v1"  # API版本号
    API_PREFIX: str = "/api"  # API前缀

    # 响应配置
    RESPONSE_CODE_SUCCESS: int = 1  # 成功响应码
    RESPONSE_CODE_ERROR: int = 0  # 错误响应码

    @property
    def ai_model_provider(self) -> str:
        provider = (self.AI_MODEL_PROVIDER or "").strip().lower()
        return AI_PROVIDER_ALIASES.get(provider, provider)

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
