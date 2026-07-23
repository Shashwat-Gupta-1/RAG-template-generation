"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";

interface AuthContextType {
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [isClient, setIsClient] = useState(false);
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    setIsClient(true);
    const storedToken = localStorage.getItem("token");
    if (storedToken) {
      setToken(storedToken);
    } else if (pathname !== "/login") {
      router.push("/login");
    }
  }, [pathname, router]);

  const login = (newToken: string) => {
    setToken(newToken);
    localStorage.setItem("token", newToken);
    router.push("/");
  };

  const logout = () => {
    setToken(null);
    localStorage.removeItem("token");
    router.push("/login");
  };

  if (!isClient) return null; // Prevent hydration mismatch

  return (
    <AuthContext.Provider value={{ token, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};
