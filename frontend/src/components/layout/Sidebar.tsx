"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import {
  MessageSquare,
  LayoutDashboard,
  BookOpen,
  BarChart3,
  Settings,
  LogOut,
  Zap,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/hooks/useAuth";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/chat", label: "AI Chat", icon: MessageSquare },
  { href: "/knowledge", label: "Knowledge Base", icon: BookOpen },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { username, logout } = useAuth();

  return (
    <aside className="flex flex-col w-56 shrink-0 border-r h-screen sticky top-0"
      style={{
        background: "var(--color-bg-subtle)",
        borderColor: "var(--color-border-subtle)",
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2.5 px-4 py-5 border-b"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <div className="w-7 h-7 rounded-lg gradient-accent flex items-center justify-center glow-accent">
          <Zap className="w-4 h-4 text-white" />
        </div>
        <span className="font-semibold text-sm tracking-tight"
          style={{ color: "var(--color-text-primary)" }}>
          VectraIQ
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
        {navItems.map(({ href, label, icon: Icon }) => {
          const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
          return (
            <Link key={href} href={href}>
              <motion.div
                whileHover={{ x: 2 }}
                transition={{ duration: 0.1 }}
                className={cn(
                  "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors relative group",
                  active
                    ? "text-white"
                    : "hover:text-white"
                )}
                style={{
                  background: active ? "var(--color-accent-glow)" : "transparent",
                  color: active ? "var(--color-text-primary)" : "var(--color-text-secondary)",
                }}
              >
                {active && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-lg"
                    style={{ background: "var(--color-accent-glow)", border: "1px solid rgba(99,102,241,0.2)" }}
                    transition={{ type: "spring", bounce: 0.2, duration: 0.3 }}
                  />
                )}
                <Icon className={cn("w-4 h-4 relative z-10 shrink-0", active && "text-indigo-400")} />
                <span className="relative z-10">{label}</span>
                {active && <ChevronRight className="w-3 h-3 ml-auto relative z-10 opacity-50" />}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* User section */}
      <div className="p-3 border-t" style={{ borderColor: "var(--color-border-subtle)" }}>
        <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg mb-1"
          style={{ background: "var(--color-bg-surface)" }}
        >
          <div className="w-6 h-6 rounded-full gradient-accent flex items-center justify-center text-xs font-semibold text-white shrink-0">
            {username?.[0]?.toUpperCase() ?? "?"}
          </div>
          <span className="text-xs font-medium truncate flex-1"
            style={{ color: "var(--color-text-secondary)" }}>
            {username ?? "Guest"}
          </span>
        </div>
        <button
          onClick={logout}
          className="w-full flex items-center gap-2.5 px-2 py-2 rounded-lg text-xs transition-colors hover:text-red-400"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
