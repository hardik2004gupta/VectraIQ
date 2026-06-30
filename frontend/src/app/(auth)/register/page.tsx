"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Zap, Eye, EyeOff, Check } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/shared/Button";

const schema = z
  .object({
    username: z
      .string()
      .min(3, "At least 3 characters")
      .max(64, "At most 64 characters")
      .regex(/^[a-z0-9_-]+$/, "Only lowercase letters, numbers, _ and -"),
    password: z.string().min(8, "At least 8 characters"),
    confirm: z.string(),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Passwords don't match",
    path: ["confirm"],
  });
type FormData = z.infer<typeof schema>;

const STRENGTH = [
  { label: "8+ characters", test: (p: string) => p.length >= 8 },
  { label: "Uppercase letter", test: (p: string) => /[A-Z]/.test(p) },
  { label: "Number", test: (p: string) => /\d/.test(p) },
  { label: "Special character", test: (p: string) => /[^a-zA-Z0-9]/.test(p) },
];

export default function RegisterPage() {
  const { register: authRegister } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const password = watch("password", "");

  const onSubmit = async (data: FormData) => {
    await authRegister(data.username, data.password);
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10"
      style={{ background: "var(--color-bg-base)" }}>
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: "radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.1), transparent)" }} />

      <div className="w-full max-w-sm relative">
        <div className="flex flex-col items-center mb-8">
          <div className="w-10 h-10 rounded-xl gradient-accent flex items-center justify-center mb-3 glow-accent">
            <Zap className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-bold" style={{ color: "var(--color-text-primary)" }}>
            Create account
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--color-text-secondary)" }}>
            Start using VectraIQ today
          </p>
        </div>

        <div className="rounded-2xl p-6"
          style={{
            background: "var(--color-bg-surface)",
            border: "1px solid var(--color-border-subtle)",
            boxShadow: "var(--shadow-elevated)",
          }}>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div>
              <label className="block text-xs font-medium mb-1.5"
                style={{ color: "var(--color-text-secondary)" }}>
                Username
              </label>
              <input
                {...register("username")}
                type="text"
                placeholder="sre-operator"
                autoComplete="username"
                className="w-full h-9 px-3 rounded-lg text-sm outline-none"
                style={{
                  background: "var(--color-bg-elevated)",
                  border: `1px solid ${errors.username ? "var(--color-error)" : "var(--color-border-default)"}`,
                  color: "var(--color-text-primary)",
                }}
              />
              {errors.username && (
                <p className="text-xs mt-1" style={{ color: "var(--color-error)" }}>
                  {errors.username.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium mb-1.5"
                style={{ color: "var(--color-text-secondary)" }}>
                Password
              </label>
              <div className="relative">
                <input
                  {...register("password")}
                  type={showPassword ? "text" : "password"}
                  placeholder="Min. 8 characters"
                  autoComplete="new-password"
                  className="w-full h-9 px-3 pr-9 rounded-lg text-sm outline-none"
                  style={{
                    background: "var(--color-bg-elevated)",
                    border: `1px solid ${errors.password ? "var(--color-error)" : "var(--color-border-default)"}`,
                    color: "var(--color-text-primary)",
                  }}
                />
                <button type="button" onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2"
                  style={{ color: "var(--color-text-tertiary)" }}>
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              {/* Password strength hints */}
              {password && (
                <div className="mt-2 space-y-1">
                  {STRENGTH.map((s) => (
                    <div key={s.label} className="flex items-center gap-1.5 text-xs">
                      <Check className={`w-3 h-3 ${s.test(password) ? "text-green-400" : ""}`}
                        style={{ color: s.test(password) ? undefined : "var(--color-text-disabled)" }} />
                      <span style={{ color: s.test(password) ? "var(--color-text-secondary)" : "var(--color-text-disabled)" }}>
                        {s.label}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              {errors.password && (
                <p className="text-xs mt-1" style={{ color: "var(--color-error)" }}>
                  {errors.password.message}
                </p>
              )}
            </div>

            <div>
              <label className="block text-xs font-medium mb-1.5"
                style={{ color: "var(--color-text-secondary)" }}>
                Confirm password
              </label>
              <input
                {...register("confirm")}
                type="password"
                placeholder="Repeat password"
                autoComplete="new-password"
                className="w-full h-9 px-3 rounded-lg text-sm outline-none"
                style={{
                  background: "var(--color-bg-elevated)",
                  border: `1px solid ${errors.confirm ? "var(--color-error)" : "var(--color-border-default)"}`,
                  color: "var(--color-text-primary)",
                }}
              />
              {errors.confirm && (
                <p className="text-xs mt-1" style={{ color: "var(--color-error)" }}>
                  {errors.confirm.message}
                </p>
              )}
            </div>

            <Button type="submit" variant="primary" size="lg" loading={isSubmitting} className="w-full mt-2">
              Create account
            </Button>
          </form>
        </div>

        <p className="text-center text-sm mt-5" style={{ color: "var(--color-text-tertiary)" }}>
          Already have an account?{" "}
          <Link href="/login" className="font-medium" style={{ color: "var(--color-accent-light)" }}>
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
