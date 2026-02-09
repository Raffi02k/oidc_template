from sqlalchemy import Boolean, Column, Integer, String
from sqlalchemy.orm import declarative_base
import enum

Base = declarative_base()

class AuthMethod(str, enum.Enum):
    LOCAL = "local"
    OIDC = "oidc"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)

    full_name = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)  # Null för OIDC users

    role = Column(String, default="User", nullable=False)

    # Spara som sträng (enklast)
    auth_method = Column(String, default=AuthMethod.LOCAL.value, nullable=False)

    oidc_id = Column(String, unique=True, index=True, nullable=True)
    oidc_tenant_id = Column(String, index=True, nullable=True)
    is_disabled = Column(Boolean, default=False, nullable=False)
