# Frontend - Hybrid Auth React Client

This is the frontend client for the Hybrid Auth Starter project. It uses React, TypeScript, and Vite.

## Features
- **MSAL Integration**: Handles OIDC login with Microsoft Entra ID.
- **Hybrid Support**: Can also log in with local credentials via the FastAPI backend.
- **Unified AuthContext**: A single context manages both OIDC and Local user sessions.
- **Role-Based Access Control**: Component-level gates and hook-based role checking.

## Key Files
- `src/auth/authConfig.ts`: MSAL configuration.
- `src/context/AuthContext.tsx`: The heart of the authentication logic.
- `src/components/RoleGate.tsx`: Protects UI elements based on user roles.

## Getting Started
1. Install dependencies: `npm install`
2. Configure `.env` (use `.env.example` as a template).
3. Start the development server: `npm run dev`

## Available Scripts
- `npm run dev`: Start dev server.
- `npm run build`: Build for production.
- `npm run preview`: Preview production build locally.
- `npm run lint`: Run ESLint.
