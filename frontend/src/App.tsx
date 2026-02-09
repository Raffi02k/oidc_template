import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { HomePage } from "./pages/HomePage";
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
};
const AppRoutes: React.FC = () => {
  const { isAuthenticated, isLoading } = useAuth();
  console.log("CLIENT_ID", import.meta.env.VITE_ENTRA_CLIENT_ID);
  console.log("TENANT_ID", import.meta.env.VITE_ENTRA_TENANT_ID);
  console.log("AUTHORITY", `https://login.microsoftonline.com/${import.meta.env.VITE_ENTRA_TENANT_ID}`);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-900 to-slate-900 text-white relative overflow-hidden">
        <div className="absolute -top-32 -left-20 h-80 w-80 rounded-full bg-indigo-500/20 blur-[120px]" />
        <div className="absolute -bottom-32 -right-10 h-96 w-96 rounded-full bg-purple-500/20 blur-[140px]" />
        <div className="relative z-10 flex items-center gap-4 rounded-2xl border border-white/10 bg-white/5 px-6 py-4 backdrop-blur-xl shadow-2xl">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-white/20 border-t-white" />
          <div className="text-sm uppercase tracking-[0.2em] text-slate-200">Loading session</div>
        </div>
      </div>
    );
  }
  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />}
      />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <HomePage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
};
function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
export default App;
