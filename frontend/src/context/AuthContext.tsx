import React, { createContext, useContext, useEffect, useState } from "react";
import { InteractionStatus, PublicClientApplication } from "@azure/msal-browser";
import { MsalProvider, useMsal } from "@azure/msal-react";
import { loginRequest, msalConfig } from "../auth/msalConfig";
import axios from "axios";

// Initialize MSAL outside to pass to provider
export const msalInstance = new PublicClientApplication(msalConfig);

export interface UnifiedUser {
    id: string; // OID for OIDC, Database ID for Local
    name: string;
    username: string;
    role: string;
    authMethod: "oidc" | "local";
    rawClaims?: any; // For debugging
    token?: string; // JWT for local, AccessToken for OIDC (if needed)
}

interface AuthContextType {
    user: UnifiedUser | null;
    isAuthenticated: boolean;
    loginLocal: (username: string, password: string) => Promise<void>;
    loginOidc: () => void;
    logout: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// Internal component to use MSAL hooks
const AuthProviderContent = ({ children }: { children: React.ReactNode }) => {
    const { instance, accounts, inProgress } = useMsal();
    const [user, setUser] = useState<UnifiedUser | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // [CRITICAL] Hybrid Auth Check:
    // 1. First, we check if an OIDC user is already logged in via MSAL (accounts.length > 0).
    // 2. If not, we check for a Local Auth JWT token in localStorage.
    // This ensures that the user session persists across reloads for both methods.
    const buildOidcUserFromAccount = (account: (typeof accounts)[number]) => {
        setUser({
            id: account.localAccountId,
            name: account.name || "",
            username: account.username,
            role: account.idTokenClaims ? String(account.idTokenClaims["roles"] ?? account.idTokenClaims["role"] ?? "User") : "User",
            authMethod: "oidc",
            rawClaims: account.idTokenClaims,
        });
    };

    useEffect(() => {
        if (inProgress !== InteractionStatus.None) return;
        const checkLocalAuth = async () => {
            const token = localStorage.getItem("local_token");
            if (token) {
                try {
                    const res = await axios.get("http://localhost:8000/me", {
                        headers: { Authorization: `Bearer ${token}` },
                    });
                    setUser({
                        id: res.data.id.toString(),
                        name: res.data.full_name || res.data.username,
                        username: res.data.username,
                        role: res.data.role,
                        authMethod: "local",
                        token: token,
                    });
                } catch (e) {
                    console.error("Local token invalid", e);
                    localStorage.removeItem("local_token");
                }
            }
            setIsLoading(false);
        };

        const checkOidcAuth = async () => {
            try {
                const account = accounts[0];
                instance.setActiveAccount(account);
                buildOidcUserFromAccount(account);
            } catch (e) {
                console.error("OIDC session found but setup failed", e);
            } finally {
                setIsLoading(false);
            }
        };
        if (accounts.length > 0) {
            setIsLoading(true);
            checkOidcAuth();
        } else {
            checkLocalAuth();
        }
    }, [instance, accounts, inProgress]);

    const loginLocal = async (username: string, password: string) => {
        setIsLoading(true);
        try {
            const formData = new FormData();
            formData.append("username", username);
            formData.append("password", password);

            const res = await axios.post("http://localhost:8000/token", formData);
            const token = res.data.access_token;
            localStorage.setItem("local_token", token);

            // Fetch User Details
            const userRes = await axios.get("http://localhost:8000/me", {
                headers: { Authorization: `Bearer ${token}` },
            });

            setUser({
                id: userRes.data.id.toString(),
                name: userRes.data.full_name || userRes.data.username,
                username: userRes.data.username,
                role: userRes.data.role,
                authMethod: "local",
                token: token,
            });
        } catch (error) {
            setIsLoading(false);
            throw error;
        }
        setIsLoading(false);
    };

    const loginOidc = async () => {
        try {
            await instance.loginRedirect(loginRequest);
        } catch (error) {
            console.error(error);
        }
    };

    const logout = () => {
        if (user?.authMethod === "oidc") {
            instance.logoutRedirect();
        } else {
            localStorage.removeItem("local_token");
            setUser(null);
            window.location.reload();
        }
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated: !!user, loginLocal, loginOidc, logout, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
    return (
        <MsalProvider instance={msalInstance}>
            <AuthProviderContent>{children}</AuthProviderContent>
        </MsalProvider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) throw new Error("useAuth must be used within an AuthProvider");
    return context;
};
