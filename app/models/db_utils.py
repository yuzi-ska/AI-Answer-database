"""
OCS网课助手数据库工具
"""
from sqlalchemy.orm import Session
from typing import Optional
from app.models import QuestionAnswer
import re


def create_question_answer(db: Session, question: str, answer: str, source: str = "unknown") -> QuestionAnswer:
    """
    创建题目答案记录
    """
    db_qa = QuestionAnswer(question=question, answer=answer, source=source)
    db.add(db_qa)
    db.commit()
    db.refresh(db_qa)
    return db_qa


def get_question_answer_by_exact_match(db: Session, question: str) -> Optional[QuestionAnswer]:
    """
    精确匹配查询题目答案
    """
    return db.query(QuestionAnswer).filter(QuestionAnswer.question == question).first()


def search_question_answer_fuzzy(db: Session, question: str) -> Optional[QuestionAnswer]:
    """
    模糊查询题目答案
    使用 LIKE 操作进行模糊匹配
    """
    # 首先尝试精确匹配
    exact_match = db.query(QuestionAnswer).filter(QuestionAnswer.question == question).first()
    if exact_match:
        return exact_match
    
    # 如果没有精确匹配，尝试模糊匹配
    # 移除可能的标点符号，进行更宽松的匹配
    import re
    # 移除标点符号并转为小写
    clean_question = re.sub(r'[^\w\s]', ' ', question.lower())
    
    # 查找包含所有关键词的记录
    keywords = [kw for kw in clean_question.split() if len(kw) > 2]  # 只考虑长度大于2的词
    
    if not keywords:
        return None
    
    # 构建查询条件，查找包含尽可能多关键词的题目
    query_result = db.query(QuestionAnswer)
    for keyword in keywords:
        query_result = query_result.filter(QuestionAnswer.question.like(f"%{keyword}%"))
    
    # 返回最匹配的结果
    result = query_result.first()
    
    # 如果上面的查询没有结果，尝试更宽松的模糊匹配
    if not result:
        # 尝试匹配至少包含部分关键词的题目
        for keyword in keywords:
            fuzzy_result = db.query(QuestionAnswer).filter(
                QuestionAnswer.question.like(f"%{keyword}%")
            ).first()
            if fuzzy_result:
                return fuzzy_result
    
    return result


def get_question_answer_by_fuzzy_search(db: Session, question: str) -> Optional[QuestionAnswer]:
    """
    使用更高级的模糊搜索算法查找题目答案
    """
    # 首先尝试精确匹配
    exact_match = get_question_answer_by_exact_match(db, question)
    if exact_match:
        return exact_match
    
    # 使用模糊搜索
    fuzzy_match = search_question_answer_fuzzy(db, question)
    return fuzzy_match