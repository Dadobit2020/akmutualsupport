"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { User, getCurrentUser, clearTokens, getAccessToken } from "./api";
import { useRouter } from "next/navigation";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  logout: () => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  logout: () => {},
  refresh: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const loadUser = async () => {
    if (!getAccessToken()) {
      setLoading(false);
      return;
    }
    try {
      const u = await getCurrentUser();
      setUser(u);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUser();
  }, []);

  const logout = () => {
    clearTokens();
    setUser(null);
    router.push("/login");
  };

  return (
    <AuthContext.Provider value={{ user, loading, logout, refresh: loadUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
