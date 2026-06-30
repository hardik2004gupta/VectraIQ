"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Server, Database, Shield, Zap, RefreshCw, Trash2, LogOut, CheckCircle2, XCircle
} from "lucide-react";
import { adminApi } from "@/lib/api";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge, ServiceDot } from "@/components/shared/StatusBadge";
import { Button } from "@/components/shared/Button";
import { useAuth } from "@/hooks/useAuth";
import { useAuthStore } from "@/store/auth";

interface SettingRowProps {
  label: string;
  value: string;
  mono?: boolean;
}

function SettingRow({ label, value, mono = false }: SettingRowProps) {
  return (
    <div className="flex items-center justify-between py-3 border-b last:border-0"
      style={{ borderColor: "var(--color-border-subtle)" }}>
      <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{label}</span>
      <span className={`text-sm ${mono ? "font-mono" : "font-medium"}`}
        style={{ color: "var(--color-text-primary)" }}>
        {value}
      </span>
    </div>
  );
}

interface SectionCardProps {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}

function SectionCard({ icon, title, children }: SectionCardProps) {
  return (
    <div className="rounded-xl border overflow-hidden"
      style={{ background: "var(--color-bg-surface)", borderColor: "var(--color-border-subtle)" }}>
      <div className="flex items-center gap-2.5 px-4 py-3 border-b"
        style={{ borderColor: "var(--color-border-subtle)", background: "var(--color-bg-elevated)" }}>
        <div className="text-indigo-400">{icon}</div>
        <h3 className="text-sm font-medium" style={{ color: "var(--color-text-primary)" }}>{title}</h3>
      </div>
      <div className="px-4">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const qc = useQueryClient();
  const { logout } = useAuth();
  const { username, isAdmin } = useAuthStore();

  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useQuery({
    queryKey: ["health"],
    queryFn: () => adminApi.health(),
    refetchInterval: 30_000,
  });

  const clearCache = useMutation({
    mutationFn: () => adminApi.cacheClear(),
    onSuccess: (data) => {
      toast.success(`Cache cleared: ${data.cleared.join(", ") || "nothing to clear"}`);
      qc.invalidateQueries({ queryKey: ["cache-stats"] });
    },
    onError: () => toast.error("Failed to clear cache"),
  });

  return (
    <div>
      <PageHeader
        title="Settings"
        description="System configuration, health status, and account management."
      />

      <div className="space-y-4">
        {/* System Health */}
        <SectionCard icon={<Server className="w-4 h-4" />} title="System Health">
          <div className="py-3 space-y-3">
            <div className="flex items-center gap-2 mb-3">
              {healthLoading ? (
                <div className="h-5 w-32 skeleton" />
              ) : health ? (
                <StatusBadge
                  status={health.status === "ok" ? "ok" : "degraded"}
                  label={health.status === "ok" ? "All systems operational" : "Service degraded"}
                  pulse={health.status === "ok"}
                />
              ) : null}
              <Button
                variant="ghost"
                size="sm"
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
                onClick={() => refetchHealth()}>
                Refresh
              </Button>
            </div>

            {health && (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                {[
                  { name: "OpenAI", healthy: health.openai, description: "LLM + Embeddings" },
                  { name: "Qdrant", healthy: health.qdrant, description: "Vector store" },
                  { name: "PostgreSQL", healthy: health.postgres, description: "Relational DB" },
                  { name: "Redis", healthy: health.redis, description: "Cache" },
                  { name: "Tavily", healthy: health.tavily, description: "Web search" },
                ].map(({ name, healthy, description }) => (
                  <div key={name}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg"
                    style={{ background: "var(--color-bg-elevated)" }}>
                    {healthy
                      ? <CheckCircle2 className="w-4 h-4 text-green-400 shrink-0" />
                      : <XCircle className="w-4 h-4 text-red-400 shrink-0" />}
                    <div>
                      <p className="text-xs font-medium" style={{ color: "var(--color-text-primary)" }}>{name}</p>
                      <p className="text-xs" style={{ color: "var(--color-text-tertiary)" }}>{description}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </SectionCard>

        {/* API Configuration */}
        <SectionCard icon={<Zap className="w-4 h-4" />} title="API Configuration">
          <div>
            <SettingRow label="API Base URL" value={process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"} mono />
            <SettingRow label="Answer Model" value="gpt-4o" />
            <SettingRow label="Grader Model" value="gpt-4o-mini" />
            <SettingRow label="Embedding Model" value="text-embedding-3-small" />
            <SettingRow label="Reranker" value="CrossEncoder (local)" />
          </div>
        </SectionCard>

        {/* Cache Management */}
        <SectionCard icon={<Database className="w-4 h-4" />} title="Cache Management">
          <div className="py-3">
            <p className="text-sm mb-3" style={{ color: "var(--color-text-secondary)" }}>
              Clears the in-memory LRU cache and resets hit/miss counters. Remote Redis
              entries are not cleared (Upstash HTTP API limitation).
            </p>
            <Button
              variant="danger"
              size="sm"
              leftIcon={<Trash2 className="w-3.5 h-3.5" />}
              loading={clearCache.isPending}
              disabled={!isAdmin}
              onClick={() => clearCache.mutate()}
              title={!isAdmin ? "Admin access required" : undefined}>
              Clear in-memory cache
            </Button>
            {!isAdmin && (
              <p className="text-xs mt-2" style={{ color: "var(--color-text-tertiary)" }}>
                Admin access required to clear cache.
              </p>
            )}
          </div>
        </SectionCard>

        {/* Account */}
        <SectionCard icon={<Shield className="w-4 h-4" />} title="Account">
          <div>
            <SettingRow label="Username" value={username ?? "—"} />
            <SettingRow label="Role" value={isAdmin ? "Administrator" : "User"} />
            <SettingRow label="Authentication" value="JWT Bearer" />
          </div>
          <div className="py-3">
            <Button
              variant="ghost"
              size="sm"
              leftIcon={<LogOut className="w-3.5 h-3.5" />}
              onClick={logout}
              className="text-red-400 hover:text-red-300">
              Sign out
            </Button>
          </div>
        </SectionCard>
      </div>
    </div>
  );
}
