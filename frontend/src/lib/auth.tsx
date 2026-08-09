import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, getToken, setRefreshToken, setSessionLostHandler, setToken } from "./api";
import type { Me } from "./types";

// While an admin is "viewing-as" a user, we stash the admin's own token here and
// run requests with the impersonation token. Exiting restores the admin token.
const ADMIN_STASH_KEY = "pharmacore_admin_access";

interface AuthState {
  user: Me | null;
  loading: boolean;
  /** True while the signed-in admin is viewing-as another user. */
  impersonating: boolean;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
  impersonate: (userId: number) => Promise<void>;
  stopImpersonating: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

interface TokenPair {
  access: string;
  refresh: string;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api<Me>("/api/auth/me"));
    } catch {
      setToken(null);
      setRefreshToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  /* When renewal fails, the api client says so and the app returns to the sign-in
     screen. Without this the user sat on a dead page watching every request
     fail, which reads as the system being broken rather than as being signed
     out. */
  useEffect(() => {
    setSessionLostHandler(() => setUser(null));
    return () => setSessionLostHandler(null);
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      const tokens = await api<TokenPair>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: identifier, password }),
      });
      localStorage.removeItem(ADMIN_STASH_KEY);
      setToken(tokens.access);
      setRefreshToken(tokens.refresh);
      setLoading(true);
      await loadMe();
    },
    [loadMe],
  );

  const logout = useCallback(() => {
    localStorage.removeItem(ADMIN_STASH_KEY);
    setToken(null);
    setRefreshToken(null);
    setUser(null);
  }, []);

  const impersonate = useCallback(
    async (userId: number) => {
      const { access } = await api<{ access: string }>("/api/auth/impersonate", {
        method: "POST",
        body: JSON.stringify({ user_id: userId }),
      });
      // Stash the admin token so we can come back, then switch to the target.
      const adminToken = getToken();
      if (adminToken) localStorage.setItem(ADMIN_STASH_KEY, adminToken);
      setToken(access);
      setLoading(true);
      await loadMe();
    },
    [loadMe],
  );

  const stopImpersonating = useCallback(async () => {
    try {
      await api<void>("/api/auth/impersonate/stop", { method: "POST" });
    } catch {
      // Even if closing the session fails server-side, restore the admin locally.
    }
    const adminToken = localStorage.getItem(ADMIN_STASH_KEY);
    localStorage.removeItem(ADMIN_STASH_KEY);
    setToken(adminToken);
    setLoading(true);
    await loadMe();
  }, [loadMe]);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      impersonating: Boolean(user?.impersonator),
      login,
      logout,
      impersonate,
      stopImpersonating,
    }),
    [user, loading, login, logout, impersonate, stopImpersonating],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
