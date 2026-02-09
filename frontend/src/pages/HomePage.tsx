import React, { useState } from "react";
import { useMsal } from "@azure/msal-react";
import { useAuth } from "../context/AuthContext";
import { RoleGate } from "../components/RoleGate";
import { TokenInspector } from "../components/TokenInspector";
import { apiTokenRequest } from "../auth/msalConfig";

export const HomePage: React.FC = () => {
    const { user, logout } = useAuth();
    const { instance, accounts } = useMsal();
    const [backendResult, setBackendResult] = useState<string | null>(null);
    const [backendError, setBackendError] = useState<string | null>(null);
    const [backendLoading, setBackendLoading] = useState(false);
    const fetchBackendUser = async () => {
        setBackendLoading(true);
        setBackendError(null);
        setBackendResult(null);

        try {
            let token: string | undefined;

            if (user?.authMethod === "oidc") {
                const account = instance.getActiveAccount() || accounts[0];
                if (!account) throw new Error("No active OIDC account");

                if (!apiTokenRequest.scopes.length) {
                    throw new Error("Missing VITE_ENTRA_API_SCOPE (API not configured)");
                }

                const result = await instance.acquireTokenSilent({
                    ...apiTokenRequest,
                    account,
                });

                token = result.accessToken;
            } else if (user?.authMethod === "local" && user.token) {
                token = user.token;
            }

            if (!token) throw new Error("No token available");

            const response = await fetch("http://localhost:8000/users", {
                headers: { Authorization: `Bearer ${token}` },
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.detail || "Backend request failed");
            }

            setBackendResult(JSON.stringify(data, null, 2));
        } catch (error) {
            const message = error instanceof Error ? error.message : "Unknown error";
            setBackendError(message);
        } finally {
            setBackendLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-slate-900 text-white p-8">
            <header className="flex justify-between items-center mb-12 border-b border-white/10 pb-6">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 to-cyan-400">
                        Internal Dashboard
                    </h1>
                    <p className="text-slate-400 mt-2">Welcome back, {user?.name}</p>
                </div>
                <button
                    onClick={logout}
                    className="bg-red-500/10 text-red-400 px-4 py-2 rounded-lg hover:bg-red-500/20 transition-colors"
                >
                    Logout
                </button>
            </header>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="col-span-1 md:col-span-2 space-y-6">
                    <RoleGate allowedRoles={["Admin", "Staff"]} fallback={<div className="p-6 bg-slate-800 rounded-xl border border-white/5">You are a generic user.</div>}>
                        <div className="p-6 bg-slate-800 rounded-xl border border-white/5">
                            <h2 className="text-xl font-semibold mb-4 text-indigo-300">Staff Area</h2>
                            <p className="text-slate-400">This content is only visible to Staff and Admins.</p>
                        </div>
                    </RoleGate>

                    <RoleGate allowedRoles={["Admin"]}>
                        <div className="p-6 bg-gradient-to-br from-indigo-900/50 to-purple-900/50 rounded-xl border border-indigo-500/30">
                            <h2 className="text-xl font-semibold mb-4 text-white">Admin Control Panel</h2>
                            <p className="text-indigo-200">Exclusive controls for Administrators.</p>
                        </div>
                    </RoleGate>
                </div>

                <div className="p-6 bg-slate-800 rounded-xl border border-white/5 h-fit">
                    <h2 className="text-lg font-semibold mb-4 text-slate-300">Your Profile</h2>
                    <div className="space-y-3 text-sm">
                        <div className="flex justify-between">
                            <span className="text-slate-500">Username</span>
                            <span className="text-slate-200">{user?.username}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-500">Role</span>
                            <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 text-xs">{user?.role}</span>
                        </div>
                        <div className="flex justify-between">
                            <span className="text-slate-500">Method</span>
                            <span className="text-slate-200 capitalize">{user?.authMethod}</span>
                        </div>
                    </div>

                    <div className="mt-6">
                        <button
                            onClick={fetchBackendUser}
                            disabled={backendLoading}
                            className="w-full bg-indigo-500/20 text-indigo-200 px-4 py-2 rounded-lg hover:bg-indigo-500/30 disabled:opacity-60"
                        >
                            {backendLoading ? "Testing backend..." : "Test backend /users"}
                        </button>
                        {backendError && (
                            <div className="mt-3 text-xs text-red-300 bg-red-500/10 border border-red-500/20 rounded p-2">
                                {backendError}
                            </div>
                        )}
                        {backendResult && (
                            <pre className="mt-3 text-xs text-green-300 bg-slate-900 p-2 rounded overflow-auto max-h-64">
                                {backendResult}
                            </pre>
                        )}
                    </div>
                </div>
            </div>

            <TokenInspector />
        </div>
    );
};
