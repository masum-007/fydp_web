"use client";

import {
  createContext, useCallback, useContext, useEffect,
  useRef, useState, type ReactNode,
} from "react";
import {
  endServerSession, loginUser, restoreSession, setAccessToken,
  type Investigator, type LoginResponse,
} from "@/services/api";

type AuthStatus = "checking" | "authenticated" | "guest";
type AuthContextType = {
  user: Investigator | null;
  token: string | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  updateUser: (user: Investigator) => void;
  clearAfterSecurityChange: () => void;
};
const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Investigator | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [status, setStatus] = useState<AuthStatus>("checking");
  const operation = useRef(0);
  const channel = useRef<BroadcastChannel | null>(null);

  const applySession = useCallback((session: LoginResponse) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    setToken(session.access_token);
    setStatus("authenticated");
  }, []);
  const clearLocalSession = useCallback(() => {
    operation.current += 1;
    setAccessToken(null);
    setUser(null);
    setToken(null);
    setStatus("guest");
  }, []);

  useEffect(() => {
    let mounted = true;
    const seq = operation.current;
    const renew = () => {
      const ticket = operation.current;
      void restoreSession().then((session) => {
        if (mounted && ticket === operation.current) applySession(session);
      }).catch(() => {
        if (mounted && ticket === operation.current) clearLocalSession();
      });
    };
    const onToken = (event: Event) => {
      if (mounted) applySession((event as CustomEvent<LoginResponse>).detail);
    };
    const onExpired = () => {
      if (mounted) clearLocalSession();
    };
    window.addEventListener("neuraledge-token-renewed", onToken);
    window.addEventListener("neuraledge-session-expired", onExpired);
    if (typeof BroadcastChannel !== "undefined") {
      const bc = new BroadcastChannel("neuraledge-session-v1");
      channel.current = bc;
      bc.onmessage = (event: MessageEvent<{ type?: string }>) => {
        if (event.data?.type === "logout") clearLocalSession();
        if (event.data?.type === "login" || event.data?.type === "profile") renew();
      };
    }
    void restoreSession().then((session) => {
      if (mounted && seq === operation.current) applySession(session);
    }).catch(() => {
      if (mounted && seq === operation.current) clearLocalSession();
    });
    return () => {
      mounted = false;
      window.removeEventListener("neuraledge-token-renewed", onToken);
      window.removeEventListener("neuraledge-session-expired", onExpired);
      channel.current?.close();
      channel.current = null;
    };
    // One bootstrap per mounting; subsequent token renewals use the event.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [applySession, clearLocalSession]);

  async function login(email: string, password: string) {
    const result = await loginUser(email, password);
    operation.current += 1;
    applySession(result);
    channel.current?.postMessage({ type: "login" });
  }

  async function logout() {
    await endServerSession();
    clearLocalSession();
    channel.current?.postMessage({ type: "logout" });
  }

  function updateUser(updated: Investigator) {
    setUser(updated);
    channel.current?.postMessage({type: "profile"});
  }
  function clearAfterSecurityChange() {
    clearLocalSession();
    channel.current?.postMessage({type: "logout"});
  }

  return (
    <AuthContext.Provider value={{ user, token, status, login, logout, updateUser, clearAfterSecurityChange }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
