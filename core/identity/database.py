# identity/database.py
import structlog
from sqlalchemy import Column, Integer, String, Float, DateTime, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

logger = structlog.get_logger("AEGIS.Identity.Database")
Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    trust_score = Column(Float, default=1.0)
    last_login = Column(DateTime, default=datetime.datetime.utcnow)

engine = create_engine('sqlite:///identity/identity.db')
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Identity database initialized.")
