
"use client";

import {
  createContext,
  useContext,
  useState,
  type ReactNode,
} from "react";

import {
  loginUser,
  type Investigator,
} from "@/services/api";

type AuthContextType = {
  user: Investigator | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextType | undefined>(
  undefined
);

export function AuthProvider({
  children,
}: {
  children: ReactNode;
}) {
  const [user, setUser] = useState<Investigator | null>(null);
  const [token, setToken] = useState<string | null>(null);

  async function login(email: string, password: string) {
    const result = await loginUser(email, password);

    setUser(result.user);
    setToken(result.access_token);
  }

  function logout() {
    setUser(null);
    setToken(null);
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}
