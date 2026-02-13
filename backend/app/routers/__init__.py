"""
API Routers - separated by concern
"""

from . import local_auth
from . import oidc_auth
from . import api as api_router

__all__ = [
    "local_auth",
    "oidc_auth",
    "api_router",
]
