from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

SQLCHEMY_DATABASE_URL = "sqlite:///./sql_app.db"
# SQLCHEMY_DATABASE_URL = "postgresql://user:password@postgresserver/db"

engine = create_engine(
    SQLCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
