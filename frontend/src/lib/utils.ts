import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatRelativeTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const diff = Date.now() - d.getTime();
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function truncate(str: string, maxLength: number): string {
  if (str.length <= maxLength) return str;
  return str.slice(0, maxLength - 3) + "…";
}

export function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function formatPercent(ratio: number, decimals = 1): string {
  return `${(ratio * 100).toFixed(decimals)}%`;
}

export function copyToClipboard(text: string): Promise<void> {
  return navigator.clipboard.writeText(text);
}

// Map backend error codes to user-facing messages
const ERROR_MESSAGES: Record<string, string> = {
  injection_detected: "Your message was blocked by our security filter. Please rephrase.",
  content_blocked: "Your message was blocked for policy reasons.",
  rate_limit_exceeded: "Too many requests. Please wait a moment and try again.",
  token_budget_exceeded: "You've reached your daily usage limit. Try again tomorrow.",
  authentication_error: "Session expired. Please log in again.",
  token_expired: "Session expired. Please log in again.",
  authorization_error: "You don't have permission to perform this action.",
  validation_error: "Please check your input and try again.",
  ai_provider_error: "AI service is temporarily unavailable. Please try again.",
  vector_store_error: "Knowledge base is temporarily unavailable.",
  database_error: "Database is temporarily unavailable.",
  internal_error: "An unexpected error occurred. Please try again.",
};

export function friendlyError(code: string, fallback?: string): string {
  return ERROR_MESSAGES[code] ?? fallback ?? "Something went wrong. Please try again.";
}
