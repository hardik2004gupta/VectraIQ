"use client";

import { useQuery } from "@tanstack/react-query";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import { TrendingUp, Zap, Activity, Database } from "lucide-react";
import { adminApi } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatCard } from "@/components/shared/Card";
import { CardSkeleton } from "@/components/shared/LoadingSkeleton";
import { Button } from "@/components/shared/Button";

const COLORS = ["#6366f1", "#8b5cf6", "#a78bfa", "#c4b5fd", "#818cf8"];

const CHART_STYLE = {
  fontSize: 11,
  fill: "#6a6a6a",
};

const TOOLTIP_STYLE = {
  contentStyle: {
    background: "#1a1a1a",
    border: "1px solid #2a2a2a",
    borderRadius: 10,
    color: "#f2f2f2",
    fontSize: 12,
  },
};

function HitRateBar({ tier, stats }: { tier: string; stats: { hits: number; misses: number; hit_rate: number } }) {
  const pct = Math.round(stats.hit_rate * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span style={{ color: "var(--color-text-secondary)" }}>{tier}</span>
        <span className="font-medium tabular-nums" style={{ color: "var(--color-text-primary)" }}>{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "var(--color-bg-elevated)" }}>
        <div
          className="h-full rounded-full gradient-accent transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <div className="flex gap-3 text-xs" style={{ color: "var(--color-text-tertiary)" }}>
        <span>{stats.hits} hits</span>
        <span>{stats.misses} misses</span>
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const { data: cacheStats, isLoading, refetch } = useQuery({
    queryKey: ["cache-stats"],
    queryFn: () => adminApi.cacheStats(),
    refetchInterval: 60_000,
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: () => adminApi.health(),
    refetchInterval: 30_000,
  });

  // Transform cache stats into chart data
  const tierLabels: Record<string, string> = {
    embedding: "Embeddings",
    rag: "RAG Answers",
    sql_gen: "SQL Gen",
    sql_result: "SQL Results",
    intent_router: "Intent Router",
  };

  const barData = cacheStats
    ? Object.entries(cacheStats).map(([k, v]) => ({
        name: tierLabels[k] ?? k,
        hits: v.hits,
        misses: v.misses,
        rate: Math.round(v.hit_rate * 100),
      }))
    : [];

  const pieData = cacheStats
    ? Object.entries(cacheStats).map(([k, v]) => ({
        name: tierLabels[k] ?? k,
        value: v.hits + v.misses,
      })).filter((d) => d.value > 0)
    : [];

  const totalHits = barData.reduce((s, d) => s + d.hits, 0);
  const totalMisses = barData.reduce((s, d) => s + d.misses, 0);
  const totalOps = totalHits + totalMisses;
  const overallRate = totalOps > 0 ? ((totalHits / totalOps) * 100).toFixed(1) : "0";

  return (
    <div>
      <PageHeader
        title="Analytics"
        description="Cache performance and system usage metrics."
        actions={
          <Button variant="secondary" size="sm" onClick={() => refetch()}>
            Refresh
          </Button>
        }
      />

      {/* Top stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {isLoading ? (
          Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)
        ) : (
          <>
            <StatCard
              label="Overall Hit Rate"
              value={`${overallRate}%`}
              icon={<Zap className="w-3.5 h-3.5 text-indigo-400" />}
              delta="across all tiers"
              deltaPositive
            />
            <StatCard
              label="Total Hits"
              value={totalHits.toLocaleString()}
              icon={<Activity className="w-3.5 h-3.5 text-green-400" />}
            />
            <StatCard
              label="Total Misses"
              value={totalMisses.toLocaleString()}
              icon={<TrendingUp className="w-3.5 h-3.5 text-yellow-400" />}
            />
            <StatCard
              label="Total Operations"
              value={totalOps.toLocaleString()}
              icon={<Database className="w-3.5 h-3.5 text-blue-400" />}
            />
          </>
        )}
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        {/* Bar chart */}
        <div className="rounded-xl p-5 border"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <h3 className="text-sm font-medium mb-4" style={{ color: "var(--color-text-primary)" }}>
            Hits vs. Misses by Tier
          </h3>
          {isLoading ? (
            <div className="h-48 skeleton rounded-lg" />
          ) : barData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm"
              style={{ color: "var(--color-text-tertiary)" }}>
              No data yet — start making queries
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={barData} barGap={4}>
                <XAxis dataKey="name" tick={CHART_STYLE} axisLine={false} tickLine={false} />
                <YAxis tick={CHART_STYLE} axisLine={false} tickLine={false} />
                <Tooltip {...TOOLTIP_STYLE} />
                <Bar dataKey="hits" fill="#6366f1" radius={[4, 4, 0, 0]} name="Hits" />
                <Bar dataKey="misses" fill="#2a2a2a" radius={[4, 4, 0, 0]} name="Misses" />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Pie chart */}
        <div className="rounded-xl p-5 border"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <h3 className="text-sm font-medium mb-4" style={{ color: "var(--color-text-primary)" }}>
            Operations by Tier
          </h3>
          {isLoading ? (
            <div className="h-48 skeleton rounded-lg" />
          ) : pieData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-sm"
              style={{ color: "var(--color-text-tertiary)" }}>
              No data yet
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  paddingAngle={4}
                  dataKey="value">
                  {pieData.map((_, index) => (
                    <Cell key={index} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...TOOLTIP_STYLE} />
                <Legend wrapperStyle={{ fontSize: 11, color: "#6a6a6a" }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Per-tier breakdown */}
      {!isLoading && cacheStats && (
        <div className="rounded-xl p-5 border"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <h3 className="text-sm font-medium mb-4" style={{ color: "var(--color-text-primary)" }}>
            Cache hit rates by tier
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {Object.entries(cacheStats).map(([k, v]) => (
              <HitRateBar key={k} tier={tierLabels[k] ?? k} stats={v} />
            ))}
          </div>
        </div>
      )}

      {/* System health summary */}
      {health && (
        <div className="mt-4 rounded-xl px-5 py-4 border"
          style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
          <p className="text-xs font-medium mb-3" style={{ color: "var(--color-text-secondary)" }}>
            System health
          </p>
          <div className="flex flex-wrap gap-4">
            {Object.entries(health)
              .filter(([k]) => k !== "status")
              .map(([k, v]) => (
                <div key={k} className="flex items-center gap-1.5 text-xs">
                  <div className={`w-1.5 h-1.5 rounded-full ${v ? "bg-green-500" : "bg-red-500"}`} />
                  <span className="capitalize" style={{ color: "var(--color-text-secondary)" }}>
                    {k}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}
