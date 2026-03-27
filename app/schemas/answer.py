"""
OCS网课助手API数据模式
"""
from typing import Optional

from pydantic import BaseModel


class QuestionRequest(BaseModel):
    """
    问题请求模式
    """
    question: str
    question_type: Optional[str] = None  # 问题类型: single, multiple, judgment, completion 等
    options: Optional[str] = None  # 选项，格式为 "A.xxx\nB.xxx\nC.xxx" 或其他格式
    use_ai: bool = True  # 是否使用AI
    use_question_bank: bool = True  # 是否使用题库
    timeout: Optional[int] = 30  # 超时时间（秒）
    thinking: Optional[bool] = None  # 是否请求深度思考；未传时按 env 默认值或不转发
    thinking_budget: Optional[int] = None  # 思考预算（仅在接口支持且配置允许时转发）
    structured_output: bool = False  # 是否请求结构化输出
    stream: bool = False  # 是否请求流式输出

    class Config:
        extra = "allow"  # 允许额外字段，兼容OCS的各种参数


class AnswerResponse(BaseModel):
    """
    答案响应模式
    """
    question: str
    answer: str
    source: str  # 来源: ai, question_bank, mixed, none
    confidence: float  # 置信度 0-1


class OCSQuestionContext(BaseModel):
    """
    OCS兼容的问题上下文
    与OCS的AnswererWrapper接口兼容
    """
    title: str  # 问题标题
    type: str  # 问题类型
    options: str  # 问题选项
    thinking: Optional[bool] = None
    thinking_budget: Optional[int] = None
    structured_output: bool = False
    stream: bool = False


class AnswererConfig(BaseModel):
    """
    题库配置模式 (OCS AnswererWrapper兼容)
    """
    url: str
    name: str
    homepage: Optional[str] = None
    data: Optional[dict] = None
    method: str = "get"
    contentType: str = "json"
    type: str = "fetch"
    headers: Optional[dict] = None
    handler: str = ""


class AnswerResult(BaseModel):
    """
    答案结果模式
    """
    question: str
    answer: str
    source: str
    confidence: float
    metadata: Optional[dict] = None
