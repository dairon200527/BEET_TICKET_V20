"""
SQLAlchemy engine/session/declarative base.

DATABASE_URL is read exclusively from the environment (see
app/core/config.py). This module never contains real credentials.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# pool_pre_ping avoids handing out dead connections after a DB restart/idle
# timeout — cheap insurance, no behavioral impact on business logic.
engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


class Base(DeclarativeBase):
    pass
