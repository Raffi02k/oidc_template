from sqlalchemy.exc import IntegrityError

from .models import User, AuthMethod
from .database import SessionLocal
from . import auth

def seed_data():
    db_session = SessionLocal()

    try:
        # Check if the user already exists
        existing_user = db_session.query(User).filter_by(username="raffi").first()
        if existing_user:
            print("Admin user already exists. Skipping seeding.")
            return

        # Create a new user
        hashed_password = auth.get_password_hash("password123")
        user = User( username="raffi", full_name="Raffi", hashed_password=hashed_password, role="Admin", auth_method=AuthMethod.LOCAL.value,)

        db_session.add(user)
        db_session.commit()
        print("Admin user created.")
    except IntegrityError as exc:
        db_session.rollback()
        print(f"Seeding failed due to IntegrityError: {exc}")
    finally:
        db_session.close()
