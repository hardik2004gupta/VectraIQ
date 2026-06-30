"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { useAuthStore } from "@/store/auth";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated());

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace("/login");
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) return null;

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 min-w-0 overflow-auto">
        <div className="max-w-6xl mx-auto px-6 py-6">
          {children}
        </div>
      </main>
    </div>
  );
}
