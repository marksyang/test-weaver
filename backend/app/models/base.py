"""SQLAlchemy 2.0 declarative base，供所有模型共用。"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """所有 ORM 模型的基類。"""

    pass
