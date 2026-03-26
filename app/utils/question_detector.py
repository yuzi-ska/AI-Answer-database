"""
题目类型识别工具
"""
import re
from typing import List


QUESTION_TYPE_ALIASES = {
    "single": "single",
    "singlechoice": "single",
    "singlequestion": "single",
    "单选": "single",
    "单选题": "single",
    "multiple": "multiple",
    "multiplechoice": "multiple",
    "multiplequestion": "multiple",
    "多选": "multiple",
    "多选题": "multiple",
    "completion": "completion",
    "fill": "completion",
    "fillblank": "completion",
    "blank": "completion",
    "填空": "completion",
    "填空题": "completion",
    "judgment": "judgment",
    "judgement": "judgment",
    "judge": "judgment",
    "boolean": "judgment",
    "truefalse": "judgment",
    "tf": "judgment",
    "对错": "judgment",
    "是非": "judgment",
    "判断": "judgment",
    "判断题": "judgment",
}


def normalize_question_type(question_type: str) -> str:
    """将外部题型归一化为内部标准值"""
    if not question_type:
        return ""

    normalized = re.sub(r"[\s\-_/]+", "", question_type).lower()
    return QUESTION_TYPE_ALIASES.get(normalized, "")


def _extract_option_values(options: str) -> List[str]:
    normalized_options = clean_question_text(options)
    if not normalized_options:
        return []

    parts = re.split(r'(?:^|[\s\r\n]+)[A-Z][\.、:：\)]\s*', normalized_options, flags=re.IGNORECASE)
    values = [part.strip().lower() for part in parts if part.strip()]
    if len(values) > 1:
        return values

    line_values = [part.strip().lower() for part in normalized_options.splitlines() if part.strip()]
    if len(line_values) > 1:
        return line_values

    separator_values = [part.strip().lower() for part in re.split(r'[；;#|/]', normalized_options) if part.strip()]
    if len(separator_values) > 1:
        return separator_values

    return values


def _has_judgment_options(options: str) -> bool:
    option_values = _extract_option_values(options)
    if len(option_values) != 2:
        return False

    option_set = {value.strip() for value in option_values}
    judgment_option_sets = [
        {"对", "错"},
        {"正确", "错误"},
        {"true", "false"},
        {"t", "f"},
        {"√", "×"},
        {"是", "否"},
        {"yes", "no"},
    ]
    return option_set in judgment_option_sets


def detect_question_type(question: str, options: str = "") -> str:
    """
    智能检测题目类型

    Args:
        question: 题目内容
        options: 选项内容（如果有）

    Returns:
        题目类型: single, multiple, judgment, completion
    """
    question = clean_question_text(question).strip()
    normalized_options = clean_question_text(options) if options else ""

    if question.startswith('【单选题】') or question.startswith('(单选题)') or question.startswith('（单选题）'):
        return "single"

    if question.startswith('【多选题】') or question.startswith('(多选题)') or question.startswith('（多选题）'):
        return "multiple"

    if question.startswith('【判断题】') or question.startswith('(判断题)') or question.startswith('（判断题）'):
        return "judgment"

    if question.startswith('【填空题】') or question.startswith('(填空题)') or question.startswith('（填空题）'):
        return "completion"

    # 如果有选项，优先判断选择/判断题
    if normalized_options:
        if "多选" in question:
            return "multiple"

        if "判断" in question or _has_judgment_options(normalized_options):
            return "judgment"

        if "单选" in question:
            return "single"

        return "single"

    # 根据题目内容判断题型
    if re.search(r'_{3,}', question) or re.search(r'（\s*\）', question) or re.search(r'\(\s*\)', question):
        return "completion"

    if "判断" in question or re.search(r'对错|正确|错误|是否|对吗', question):
        return "judgment"

    if "多选" in question:
        return "multiple"

    if "单选" in question:
        return "single"

    if re.search(r'_{2,}|\(\s*\)|（\s*\）', question):
        return "completion"

    return "completion"


def clean_question_text(text: str) -> str:
    """
    清理题目文本，保留原始内容，只去除HTML标签和多余空白
    
    Args:
        text: 原始文本
    
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 去除HTML标签和JavaScript代码
    text = remove_html_and_js(text)
    
    # 去除首尾空白
    text = text.strip()
    
    # 将连续的换行符替换为单个换行符
    text = re.sub(r'\n+', '\n', text)
    
    # 将连续的空格替换为单个空格
    text = re.sub(r' +', ' ', text)
    
    # 去除制表符
    text = text.replace('\t', '')
    
    return text


def remove_html_and_js(text: str) -> str:
    """
    移除HTML标签和JavaScript代码
    
    Args:
        text: 包含HTML/JS的文本
    
    Returns:
        清理后的文本
    """
    if not text:
        return ""
    
    # 只移除HTML标签（保留文本内容）
    text = re.sub(r'<[^>]*>', '', text)
    
    # 移除JavaScript代码块
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除CSS样式块
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除常见的无意义字符
    text = re.sub(r'点击上传.*', '', text)
    
    return text


def normalize_answer_for_type(answer: str, question_type: str, options: str = "") -> str:
    """
    根据题目类型标准化答案格式
    
    Args:
        answer: 原始答案
        question_type: 题目类型 (single, multiple, completion, judgment)
        options: 选项内容（选择题用）
    
    Returns:
        标准化后的答案
    """
    if not answer:
        return ""
    
    answer = answer.strip()
    q_type = normalize_question_type(question_type) or (question_type.lower() if question_type else "")
    
    # 单选题 - 只返回选项字母
    if q_type == "single":
        # 如果已经是单个字母，直接返回
        if re.match(r'^[A-Z]$', answer):
            return answer
        # 清理答案，提取第一个遇到的选项字母
        match = re.search(r'[A-Z]', answer)
        if match:
            return match.group()
        return answer
    
    # 多选题 - 返回用#连接的选项字母
    if q_type == "multiple":
        # 如果已经是#连接的字母格式，直接返回
        if re.match(r'^[A-Z#]+$', answer):
            return answer
        # 提取所有选项字母
        letters = re.findall(r'[A-Z]', answer)
        if letters:
            return '#'.join(letters)
        return answer
    
    # 填空题 - 直接返回答案内容
    if q_type == "completion":
        return clean_question_text(answer)
    
    # 判断题 - 标准化为 对/错
    if q_type == "judgment":
        if answer in ["对", "正确", "√", "T", "true", "True", "是", "yes"]:
            return "对"
        elif answer in ["错", "错误", "×", "F", "false", "False", "否", "no"]:
            return "错"
        return answer
    
    # 默认返回清理后的答案
    return clean_question_text(answer)