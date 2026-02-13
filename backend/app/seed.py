from .models import User, AuthMethod
from .db import SessionLocal
from .auth import local_jwt

def seed_data():
    db_session = SessionLocal()

    try:
        # Check if the user already exists
        existing_user = db_session.query(User).filter(User.username == "raffi").first()
        if existing_user:
            print("Admin user already exists. Skipping seeding.")
            return

        # Create a new user
        hashed_password = local_jwt.get_password_hash("password123")
        user = User( username="raffi", full_name="Raffi", hashed_password=hashed_password, role="Admin", auth_method=AuthMethod.LOCAL.value,)

        db_session.add(user)
        db_session.commit()
        print("Admin user created.")
    except IntegrityError as exc:
        db_session.rollback()
        print(f"Seeding failed due to IntegrityError: {exc}")
    finally:
        db_session.close()
