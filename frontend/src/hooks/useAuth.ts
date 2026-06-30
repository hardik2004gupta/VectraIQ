"use client";

import { useCallback } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { authApi, VectraIQAPIError } from "@/lib/api";
import { useAuthStore } from "@/store/auth";
import { friendlyError } from "@/lib/utils";

// Decode a JWT payload (base64url) without verification
function decodeJwtPayload(token: string): { sub?: string; is_admin?: boolean } {
  try {
    const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(base64));
  } catch {
    return {};
  }
}

export function useAuth() {
  const router = useRouter();
  const store = useAuthStore();

  const login = useCallback(
    async (username: string, password: string) => {
      try {
        const res = await authApi.login(username, password);
        const payload = decodeJwtPayload(res.token);
        store.setAuth(res.token, username, !!payload.is_admin, res.expires_in);
        router.push("/dashboard");
        toast.success("Welcome back!");
      } catch (err) {
        const code = err instanceof VectraIQAPIError ? err.code : "internal_error";
        const msg = friendlyError(code, "Login failed. Check your credentials.");
        toast.error(msg);
        throw err;
      }
    },
    [router, store]
  );

  const register = useCallback(
    async (username: string, password: string) => {
      try {
        const res = await authApi.register(username, password);
        const payload = decodeJwtPayload(res.token);
        store.setAuth(res.token, username, !!payload.is_admin, res.expires_in);
        router.push("/dashboard");
        toast.success("Account created! Welcome to VectraIQ.");
      } catch (err) {
        const code = err instanceof VectraIQAPIError ? err.code : "internal_error";
        const msg = friendlyError(code, "Registration failed. Please try again.");
        toast.error(msg);
        throw err;
      }
    },
    [router, store]
  );

  const logout = useCallback(() => {
    store.clearAuth();
    router.push("/login");
    toast.info("Logged out");
  }, [router, store]);

  return {
    isAuthenticated: store.isAuthenticated(),
    username: store.username,
    isAdmin: store.isAdmin,
    login,
    register,
    logout,
  };
}
