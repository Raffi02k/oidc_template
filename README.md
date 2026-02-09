# Hybrid Auth Starter (Vite + FastAPI)

Production-ready starter with **two auth paths**:
- **OIDC (Microsoft Entra ID)** in the frontend using MSAL
- **Local username/password** in the backend (JWT)

It includes a unified `User` model in the React `AuthContext`, RBAC helpers, and optional backend protection using Entra access tokens.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![React](https://img.shields.io/badge/frontend-React_18-61DAFB.svg)
![FastAPI](https://img.shields.io/badge/backend-FastAPI-009688.svg)
![Tailwind](https://img.shields.io/badge/style-Tailwind_CSS-38B2AC.svg)

## Features
- Dual auth (OIDC + Local)
- Unified user shape in `AuthContext`
- RBAC via `<RoleGate allowedRoles={['Admin']} />`
- Token inspector for debugging
- Vite + FastAPI dev flow

## Tech Stack
### Frontend
- React 18 + TypeScript + Vite
- Tailwind CSS
- MSAL (`@azure/msal-browser`, `@azure/msal-react`)

### Backend
- FastAPI
- SQLAlchemy + SQLite
- JWT for local auth (`python-jose`, `passlib[bcrypt]`)

## Getting Started
### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` in `backend/`:
```env
SECRET_KEY=change_me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Required only if validating OIDC access tokens
OIDC_ISSUER=https://login.microsoftonline.com/<TENANT_ID>/v2.0,https://sts.windows.net/<TENANT_ID>/
OIDC_AUDIENCE=<API-CLIENT-ID-or-App-ID-URI>
OIDC_JWKS_URL=https://login.microsoftonline.com/<TENANT_ID>/discovery/v2.0/keys

# OIDC policy (minimal)
OIDC_REQUIRED_SCOPES=access_as_user
OIDC_JWKS_CACHE_TTL_SECONDS=3600

# Dev-only setup endpoint
ENABLE_DEV_SETUP=true

# CORS
CORS_ALLOWED_ORIGINS=https://your-frontend.example.com
```

Start the API:
```bash
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.example .env
```

Edit `frontend/.env`:
```env
VITE_ENTRA_CLIENT_ID=<SPA-CLIENT-ID>
VITE_ENTRA_TENANT_ID=<TENANT-ID>

# Optional, required only if calling backend with OIDC access tokens
VITE_ENTRA_API_SCOPE=api://<API-CLIENT-ID>/access_as_user
```

Start the UI:
```bash
npm run dev
```

## Usage
### Local Auth (JWT)
Seed a default local admin:
```bash
curl -X POST http://localhost:8000/setup
```

Login with:
- username: `admin`
- password: `password123`

### OIDC Login (Frontend)
Use **Sign in with Microsoft**. MSAL handles login and user identity in the UI.

### OIDC Access Token to Backend (Optional)
If you want to protect API endpoints with Entra tokens:
1. Create an **API App Registration** and expose a scope (e.g. `access_as_user`).
2. Set `VITE_ENTRA_API_SCOPE` in the frontend.
3. Set `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL` in the backend.

Then call protected endpoints with `Authorization: Bearer <access_token>`.

## Project Structure
```bash
/
├── backend/
│   ├── app/
│   │   ├── auth.py          # JWT + OIDC helpers
│   │   ├── models.py        # SQLAlchemy User model
│   │   ├── routes.py        # API endpoints (/token, /me, /users)
│   │   └── main.py          # FastAPI app + CORS
│   └── sql_app.db           # SQLite database (local)
├── frontend/
│   ├── src/
│   │   ├── auth/            # MSAL config + claims helpers
│   │   ├── context/         # AuthContext (unified user)
│   │   ├── components/      # RoleGate, TokenInspector, UI blocks
│   │   ├── pages/           # LoginPage, HomePage
│   │   └── App.tsx          # Router + auth guards
└── README.md
```

## Security Notes
- Keep `SECRET_KEY` secret and rotate in production.
- Local JWTs are stored in `localStorage` (simple dev flow). For higher security, consider HttpOnly cookies.

## Production Checklist
- Set `CORS_ALLOWED_ORIGINS` to your real frontend domains.
- Require scopes via `OIDC_REQUIRED_SCOPES`.
- Use API scopes (`VITE_ENTRA_API_SCOPE`) and access tokens for backend protection.
- Disable dev setup endpoint (`ENABLE_DEV_SETUP=false`).
- Add database migration for `is_disabled` and manage account lockouts.

## License
MIT
