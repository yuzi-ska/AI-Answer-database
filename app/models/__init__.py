"""
OCS网课助手数据库模型
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os
from app.core.config import settings


# 创建基础模型类
Base = declarative_base()


class QuestionAnswer(Base):
    """
    题目答案表模型
    """
    __tablename__ = "question_answers"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(String, index=True)  # 题目内容
    question_type = Column(String, index=True)  # 题目类型 (single, multiple, judgment, completion等)
    options = Column(Text)  # 选项内容
    answer = Column(Text)  # 答案内容
    source = Column(String, default="unknown")  # 来源 (ai, question_bank, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)  # 创建时间
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 更新时间


# 创建数据库引擎
engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {})

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables():
    """创建所有表"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()