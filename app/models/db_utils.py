"""
OCS网课助手数据库工具
"""
from sqlalchemy.orm import Session
from typing import Optional, List
from app.models import QuestionAnswer
import re


def create_question_answer(db: Session, question: str, answer: str, source: str = "unknown", question_type: str = "", options: str = "") -> QuestionAnswer:
    """
    创建题目答案记录
    """
    db_qa = QuestionAnswer(question=question, question_type=question_type, options=options, answer=answer, source=source)
    db.add(db_qa)
    db.commit()
    db.refresh(db_qa)
    return db_qa


def get_question_answer_by_exact_match(db: Session, question: str) -> Optional[QuestionAnswer]:
    """
    精确匹配查询题目答案（仅题目）
    """
    return db.query(QuestionAnswer).filter(QuestionAnswer.question == question).first()


def normalize_options(options: str) -> str:
    """
    标准化选项格式，去除多余空格和换行
    """
    if not options:
        return ""
    # 去除每行前后空格，然后用换行符连接
    lines = [line.strip() for line in options.split("\n") if line.strip()]
    return "\n".join(lines)


def get_question_answer_by_full_match(db: Session, question: str, question_type: str = "", options: str = "") -> Optional[QuestionAnswer]:
    """
    完全匹配查询题目答案（题目、类型和选项）
    只有当题目、类型和选项完全一致时才返回结果
    """
    query = db.query(QuestionAnswer).filter(QuestionAnswer.question == question)
    
    # 添加类型过滤条件 - 这是关键区分点
    if question_type:
        query = query.filter(QuestionAnswer.question_type == question_type)
    
    # 标准化选项格式
    normalized_options = normalize_options(options)
    
    # 添加选项过滤条件
    if normalized_options:
        query = query.filter(QuestionAnswer.options == normalized_options)
    else:
        # 如果没有提供选项，则查找选项为空的记录
        query = query.filter(QuestionAnswer.options == "" )
    
    return query.first()


def get_all_question_answers_by_question(db: Session, question: str) -> List[QuestionAnswer]:
    """
    获取同一题目的所有不同题型答案
    用于返回同一题目的多种题型答案（如填空题和选择题版本）
    """
    return db.query(QuestionAnswer).filter(QuestionAnswer.question == question).all()