"use client";

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { MessageSquare, BookOpen, Zap, TrendingUp, ArrowRight, Database, Activity } from "lucide-react";
import Link from "next/link";
import { adminApi } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/shared/Card";
import { StatusBadge, ServiceDot } from "@/components/shared/StatusBadge";
import { CardSkeleton } from "@/components/shared/LoadingSkeleton";
import { useAuthStore } from "@/store/auth";

const QUICK_ACTIONS = [
  {
    href: "/chat",
    icon: MessageSquare,
    label: "Ask a question",
    description: "Start an AI-powered Q&A session",
    gradient: "from-indigo-500 to-violet-600",
  },
  {
    href: "/knowledge",
    icon: BookOpen,
    label: "Upload documents",
    description: "Add runbooks and documentation",
    gradient: "from-violet-500 to-purple-600",
  },
  {
    href: "/analytics",
    icon: TrendingUp,
    label: "View analytics",
    description: "Cache hits, latency, usage trends",
    gradient: "from-blue-500 to-indigo-600",
  },
];

export default function DashboardPage() {
  const username = useAuthStore((s) => s.username);
  const router = useRouter();

  const { data: health, isLoading: healthLoading } = useQuery({
    queryKey: ["health"],
    queryFn: () => adminApi.health(),
    refetchInterval: 30_000,
  });

  const { data: cacheStats, isLoading: cacheLoading } = useQuery({
    queryKey: ["cache-stats"],
    queryFn: () => adminApi.cacheStats(),
    refetchInterval: 60_000,
  });

  const totalHits = cacheStats
    ? Object.values(cacheStats).reduce((s, t) => s + t.hits, 0)
    : 0;
  const totalMisses = cacheStats
    ? Object.values(cacheStats).reduce((s, t) => s + t.misses, 0)
    : 0;
  const hitRate = totalHits + totalMisses > 0
    ? ((totalHits / (totalHits + totalMisses)) * 100).toFixed(1)
    : "—";

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${username ?? "user"}`}
        description="Your AI Knowledge Platform is ready."
      />

      {/* System status bar */}
      <div className="flex items-center gap-3 mb-6 px-4 py-3 rounded-xl"
        style={{ background: "var(--color-bg-surface)", border: "1px solid var(--color-border-subtle)" }}>
        {healthLoading ? (
          <div className="h-4 w-32 skeleton" />
        ) : health ? (
          <>
            <StatusBadge
              status={health.status === "ok" ? "ok" : "degraded"}
              label={health.status === "ok" ? "All systems operational" : "Degraded"}
              pulse={health.status === "ok"}
            />
            <span className="text-xs" style={{ color: "var(--color-border-default)" }}>|</span>
            <div className="flex items-center gap-4 flex-wrap">
              <ServiceDot healthy={health.openai} name="OpenAI" />
              <ServiceDot healthy={health.qdrant} name="Qdrant" />
              <ServiceDot healthy={health.postgres} name="Postgres" />
              <ServiceDot healthy={health.redis} name="Redis" />
            </div>
          </>
        ) : (
          <span className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
            Status unavailable
          </span>
        )}
        <Link href="/settings" className="ml-auto text-xs flex items-center gap-1"
          style={{ color: "var(--color-text-tertiary)" }}>
          Details <ArrowRight className="w-3 h-3" />
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {cacheLoading ? (
          Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              label="Cache Hit Rate"
              value={hitRate === "—" ? "—" : `${hitRate}%`}
              icon={<Zap className="w-3.5 h-3.5 text-indigo-400" />}
              delta={hitRate !== "—" ? "vs. no-cache" : undefined}
              deltaPositive
            />
            <StatCard
              label="Total Cached"
              value={totalHits.toLocaleString()}
              icon={<Activity className="w-3.5 h-3.5 text-green-400" />}
              suffix="hits"
            />
            <StatCard
              label="Embedding Hits"
              value={cacheStats?.embedding.hit_rate !== undefined
                ? `${(cacheStats.embedding.hit_rate * 100).toFixed(0)}%`
                : "—"}
              icon={<Database className="w-3.5 h-3.5 text-blue-400" />}
            />
            <StatCard
              label="RAG Hits"
              value={cacheStats?.rag.hit_rate !== undefined
                ? `${(cacheStats.rag.hit_rate * 100).toFixed(0)}%`
                : "—"}
              icon={<MessageSquare className="w-3.5 h-3.5 text-violet-400" />}
            />
          </>
        )}
      </div>

      {/* Quick actions */}
      <div>
        <h2 className="text-sm font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
          Quick actions
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {QUICK_ACTIONS.map(({ href, icon: Icon, label, description, gradient }) => (
            <button
              key={href}
              onClick={() => router.push(href)}
              className="text-left p-4 rounded-xl border transition-all hover:scale-[1.01] group"
              style={{
                background: "var(--color-bg-surface)",
                borderColor: "var(--color-border-subtle)",
              }}>
              <div className={`w-8 h-8 rounded-lg bg-gradient-to-br ${gradient} flex items-center justify-center mb-3 shadow-lg`}>
                <Icon className="w-4 h-4 text-white" />
              </div>
              <p className="text-sm font-medium mb-0.5" style={{ color: "var(--color-text-primary)" }}>
                {label}
              </p>
              <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>
                {description}
              </p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
