## Backend - Rame Plannering API
FastAPI-baserad backend med hybrid autentisering (Lokal JWT + OIDC).

### Architecture
```text
backend/
├── app/
│   ├── auth/               # Autentiseringsmodul
│   │   ├── __init__.py    # Hybrid auth orchestration 
│   │   ├── local_jwt.py   # JWT token-hantering
│   │   └── oidc.py        # OIDC/Microsoft Entra ID
│   ├── routers/           # API endpoints
│   │   ├── api.py         # Huvuddata (units, staff, schedule)
│   │   ├── local_auth.py  # /token endpoint
│   │   └── oidc_auth.py   # /oidc/me endpoint
│   ├── models.py          # SQLAlchemy datamodeller
│   ├── schemas.py         # Pydantic scheman
│   ├── db.py              # Databaskonfiguration
│   ├── seed.py            # Databasinitiering  
│   └── main.py            # FastAPI app
└── requirements.txt
```

### Claims We Use (Entra ID)
- `oid`: Stable user id in the tenant. Preferred primary key (`oidc_id`).
- `sub`: Token subject. Fallback when `oid` is missing.
- `preferred_username`: Often the login name (usually email). Used as email/username fallback.
- `name`: Display name. Good for `full_name`, not as an id.
- `tid`: Tenant id. Stored as `oidc_tenant_id` to keep a stable tenant anchor.

### Why API Scope Matters
If you call the backend with an access token, the token must be **issued for your API**:
- `aud` (audience) must match your API app id / App ID URI
- `iss` (issuer) must match your tenant
- signature must be valid (JWKS)
- `exp` must be valid

If you only request `User.Read` or other Graph scopes, the access token's `aud` is **Microsoft Graph**, not your API. The backend should reject that token.

### Client ID vs API Scope vs App ID URI
- **VITE_ENTRA_CLIENT_ID**: SPA client id used by MSAL to sign in.
- **API Client ID**: The app registration representing your API.
- **VITE_ENTRA_API_SCOPE**: The specific permission your SPA requests, usually:
  `api://<API-CLIENT-ID>/access_as_user`

### Typical API Token Flow
1. SPA signs in and gets an ID token for UI identity.
2. SPA requests an **access token** for your API scope.
3. SPA calls backend with `Authorization: Bearer <access_token>`.
4. Backend validates `iss`, `aud`, `exp`, signature via JWKS.

### Can One Scope Be Reused Across Projects?
- **Same API, multiple frontends**: Yes. Authorize multiple SPA clients to request the same API scope.
- **Different APIs**: No. Each API should have its own app registration and scopes.

### Local Dev: Default User
Seed a local admin user:

```bash
curl -X POST http://localhost:8000/setup
```

Login:
- username: `raffi`
- password: `password123`

### Required Backend Env
Create a `.env` in `backend/`:

```env
SECRET_KEY=change_me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Required only if you validate OIDC access tokens
OIDC_ISSUER=https://login.microsoftonline.com/<TENANT_ID>/v2.0,https://sts.windows.net/<TENANT_ID>/
OIDC_AUDIENCE=<API-CLIENT-ID-or-App-ID-URI>
OIDC_JWKS_URL=https://login.microsoftonline.com/<TENANT_ID>/discovery/v2.0/keys
OIDC_REQUIRED_SCOPES=access_as_user
OIDC_JWKS_CACHE_TTL_SECONDS=3600
```
