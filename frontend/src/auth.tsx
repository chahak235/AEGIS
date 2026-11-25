// Login state shared by the whole app (React "context").
// Any component can ask useAuth() for the current user, login() or logout().

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { api, hasToken, setToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  checking: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(hasToken());

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  // If the API ever answers 401 (token expired), log out everywhere.
  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  // On page load: if a token was saved, check it's still valid.
  useEffect(() => {
    if (!hasToken()) return;
    api.me()
      .then(setUser)
      .catch(() => logout())
      .finally(() => setChecking(false));
  }, [logout]);

  const login = useCallback(async (username: string, password: string) => {
    const { access_token } = await api.login(username, password);
    setToken(access_token);
    setUser(await api.me());
  }, []);

  const value = useMemo(() => ({ user, checking, login, logout }), [user, checking, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/** Shows its children only to logged-in users; everyone else goes to /login.
 *  NOTE: this is for convenience only. Real protection is the backend refusing
 *  requests without a valid token. Hiding a page is not security. */
export function RequireAuth({ children, role }: { children: ReactNode; role?: "admin" }) {
  const { user, checking } = useAuth();
  const location = useLocation();
  if (checking) return <div className="center muted">Checking your session…</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (role && user.role !== role) return <div className="center">This page is for admins only.</div>;
  return <>{children}</>;
}
