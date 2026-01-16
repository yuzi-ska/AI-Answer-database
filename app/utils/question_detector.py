"""
题目类型识别工具
"""
import re
from typing import Optional


def detect_question_type(question: str, options: str = "") -> str:
    """
    智能检测题目类型
    
    Args:
        question: 题目内容
        options: 选项内容（如果有）
    
    Returns:
        题目类型: single, multiple, judgment, completion
    """
    question = question.strip()
    
    # 1. 如果有选项，优先判断为选择题
    if options and options.strip():
        # 检查是否是多选题
        if re.search(r'[（\(][\s多选\s][）\)]', question) or re.search(r'[多选]', question):
            return "multiple"
        
        # 检查是否是判断题
        if re.search(r'[（\(][\s判断\s][）\)]', question) or re.search(r'[判断]', question):
            return "judgment"
        
        # 检查是否是单选题
        if re.search(r'[（\(][\s单选\s][）\)]', question) or re.search(r'[单选]', question):
            return "single"
        
        # 如果有选项但没有明确标识，默认为单选题
        return "single"
    
    # 2. 根据题目内容判断题型
    
    # 填空题检测 - 查找填空标记
    if re.search(r'_{3,}', question) or re.search(r'（\s*\）', question) or re.search(r'\(\s*\)', question):
        return "completion"
    
    # 判断题检测
    if re.search(r'[（\(][\s判断\s][）\)]', question) or re.search(r'[对错]|正确|错误|是否|对吗', question):
        return "judgment"
    
    # 多选题检测
    if re.search(r'[（\(][\s多选\s][）\)]', question) or re.search(r'[多选]', question):
        return "multiple"
    
    # 单选题检测
    if re.search(r'[（\(][\s单选\s][）\)]', question) or re.search(r'[单选]', question):
        return "single"
    
    # 3. 根据题目格式判断
    
    # 如果题目以"【单选题】"开头
    if question.startswith('【单选题】') or question.startswith('(单选题)'):
        return "single"
    
    # 如果题目以"【多选题】"开头
    if question.startswith('【多选题】') or question.startswith('(多选题)'):
        return "multiple"
    
    # 如果题目以"【判断题】"开头
    if question.startswith('【判断题】') or question.startswith('(判断题)'):
        return "judgment"
    
    # 如果题目以"【填空题】"开头
    if question.startswith('【填空题】') or question.startswith('(填空题)'):
        return "completion"
    
    # 4. 默认判断
    # 如果题目中有填空标记，认为是填空题
    if re.search(r'_{2,}|\(\s*\)|（\s*\）', question):
        return "completion"
    
    # 如果没有明确标识且没有选项，默认为填空题
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
    q_type = question_type.lower() if question_type else ""
    
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