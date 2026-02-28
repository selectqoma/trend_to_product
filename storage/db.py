from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

engine = create_engine("sqlite:///storage/runs.db", echo=False)
Session = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    topic = Column(String(256), nullable=True)
    status = Column(String(32), default="running")  # running | success | error
    error = Column(Text, nullable=True)


class Trend(Base):
    __tablename__ = "trends"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, nullable=False)
    source = Column(String(64))
    title = Column(Text)
    url = Column(Text, nullable=True)
    score = Column(Integer, nullable=True)
    extra = Column(JSON, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(engine)
