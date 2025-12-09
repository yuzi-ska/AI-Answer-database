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
    清理题目文本，去除无意义的换行符、HTML/JavaScript代码和多余空格
    
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
    
    # 去除换行符前后的空格
    text = re.sub(r' *\n *', '\n', text)
    
    # 去除常见的无意义换行
    text = re.sub(r'\n([，。！？；：])', r'\1', text)  # 标点符号前的换行
    text = re.sub(r'([，。！？；：])\n', r'\1', text)  # 标点符号后的换行
    
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
    
    # 移除HTML标签
    text = re.sub(r'<[^>]*>', '', text)
    
    # 移除JavaScript代码块
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>', '', text, flags=re.IGNORECASE)
    
    # 移除CSS样式
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 移除JavaScript代码行
    text = re.sub(r'window\.[A-Za-z_][A-Za-z0-9_]*.*?;', '', text)
    text = re.sub(r'var\s+[A-Za-z_][A-Za-z0-9_]*.*?=.*?;', '', text)
    text = re.sub(r'function\s+[A-Za-z_][A-Za-z0-9_]*.*?\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'addEventListener.*?;', '', text)
    text = re.sub(r'getElementById.*?;', '', text)
    text = re.sub(r'UEDITOR_CONFIG.*?;', '', text)
    text = re.sub(r'UE\.getEditor.*?\);', '', text)
    text = re.sub(r'editor1\..*?\);', '', text)
    text = re.sub(r'loadEditorAnswerd.*?\);', '', text)
    text = re.sub(r'answerContentChange.*?\);', '', text)
    text = re.sub(r'editorPaste.*?\);', '', text)
    text = re.sub(r'beforepaste.*?\);', '', text)
    text = re.sub(r'contentChange.*?\);', '', text)
    text = re.sub(r'initialFrameWidth.*?;', '', text)
    text = re.sub(r'initialFrameHeight.*?;', '', text)
    text = re.sub(r'toolbars.*?;', '', text)
    text = re.sub(r'pasteplain.*?;', '', text)
    text = re.sub(r'disablePasteImage.*?;', '', text)
    text = re.sub(r'disableDraggable.*?;', '', text)
    text = re.sub(r'parseInt.*?;', '', text)
    text = re.sub(r'allowPaste.*?;', '', text)
    
    # 移除剩余的JavaScript片段
    text = re.sub(r'if\s*\(.*?\)\s*\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\.[A-Za-z_][A-Za-z0-9_]*.*?\)', '', text)
    text = re.sub(r'[A-Za-z_][A-Za-z0-9_]*\.', '', text)
    text = re.sub(r'\{.*?\}', '', text, flags=re.DOTALL)
    text = re.sub(r'\(.*?\)', '', text, flags=re.DOTALL)
    
    # 移除常见的无意义字符和模式
    text = re.sub(r'点击上传.*', '', text)
    text = re.sub(r'x\s*$', '', text)  # 行尾的x
    text = re.sub(r'^[\s\t]*', '', text)  # 行首的空白
    text = re.sub(r'[\s\t]*$', '', text)  # 行尾的空白
    
    # 移除大括号和括号内容
    text = re.sub(r'\{[^}]*\}', '', text)
    text = re.sub(r'\([^)]*\)', '', text)
    
    # 移除引号内容
    text = re.sub(r'["\'][^"\']*["\']', '', text)
    
    # 移除常见的无意义单词
    text = re.sub(r'\b(true|false|null|undefined)\b', '', text, flags=re.IGNORECASE)
    
    # 移除剩余的JavaScript变量和函数名
    text = re.sub(r'\b[A-Za-z_][A-Za-z0-9_]*\b', '', text)
    
    # 移除剩余的符号
    text = re.sub(r'[;.,\[\]{}()]', '', text)
    
    # 多个空格和换行符替换为单个空格
    text = re.sub(r'\s+', ' ', text)
    
    # 如果清理后内容少于5个字符且不是有意义的中文，返回空字符串
    if len(text) < 5 and not re.search(r'[\u4e00-\u9fff]', text):
        return ""
    
    return text.strip()


def normalize_answer_for_type(answer: str, question_type: str, options: str = "") -> str:
    """
    根据题目类型标准化答案格式
    
    Args:
        answer: 原始答案
        question_type: 题目类型
        options: 选项内容（选择题用）
    
    Returns:
        标准化后的答案
    """
    if not answer:
        return ""
    
    answer = answer.strip()
    
    # 填空题 - 直接返回答案内容，不进行选项字母提取
    if question_type == "completion":
        cleaned_answer = clean_question_text(answer)
        # 确保填空题答案不是单个选项字母
        if re.match(r'^[A-Z]$', cleaned_answer) and options:
            # 如果答案只是单个字母且有选项，可能是错误识别，返回原答案
            return answer
        return cleaned_answer
    
    # 判断题 - 标准化为 对/错 或 正确/错误
    if question_type == "judgment":
        if answer in ["对", "正确", "√", "T", "true", "True"]:
            return "对"
        elif answer in ["错", "错误", "×", "F", "false", "False"]:
            return "错"
        return answer
    
    # 选择题 - 提取选项字母
    if question_type in ["single", "multiple"]:
        # 如果答案是单个字母或用#连接的多个字母，直接返回
        if re.match(r'^[A-Z#]+$', answer):
            return answer
        
        # 尝试从答案中提取选项字母
        if options:
            # 解析选项
            option_lines = [line.strip() for line in options.split('\n') if line.strip()]
            option_map = {}
            for line in option_lines:
                match = re.match(r'^([A-Z])[.\s、]\s*(.+)', line)
                if match:
                    option_map[match.group(2)] = match.group(1)
            
            # 在答案中查找选项内容
            for option_text, option_letter in option_map.items():
                if option_text in answer:
                    if question_type == "multiple":
                        # 多选题需要收集所有匹配的选项
                        return answer  # 保持原样，让AI处理
                    else:
                        return option_letter
        
        # 如果无法提取，返回原答案
        return answer
    
    # 其他类型直接返回清理后的答案
    return clean_question_text(answer)