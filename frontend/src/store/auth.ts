"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface AuthState {
  token: string | null;
  username: string | null;
  isAdmin: boolean;
  expiresAt: number | null; // Unix timestamp ms

  setAuth: (token: string, username: string, isAdmin: boolean, expiresIn: number) => void;
  clearAuth: () => void;
  isAuthenticated: () => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      username: null,
      isAdmin: false,
      expiresAt: null,

      setAuth: (token, username, isAdmin, expiresIn) =>
        set({
          token,
          username,
          isAdmin,
          expiresAt: Date.now() + expiresIn * 1000,
        }),

      clearAuth: () =>
        set({ token: null, username: null, isAdmin: false, expiresAt: null }),

      isAuthenticated: () => {
        const { token, expiresAt } = get();
        if (!token) return false;
        if (expiresAt && Date.now() > expiresAt) {
          get().clearAuth();
          return false;
        }
        return true;
      },
    }),
    {
      name: "vectraiq_auth",
      partialize: (s) => ({
        token: s.token,
        username: s.username,
        isAdmin: s.isAdmin,
        expiresAt: s.expiresAt,
      }),
    }
  )
);
