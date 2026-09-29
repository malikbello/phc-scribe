"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

// Small shared UI pieces: icons (inline SVG, no external assets), progress ring and
// bar, top bar, toast and a lightweight celebration burst.

type IconProps = { className?: string };
const base = "h-5 w-5 shrink-0";

export const Icon = {
  Check: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
  ),
  X: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" aria-hidden><path d="M6 6l12 12M18 6L6 18" /></svg>
  ),
  Question: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden><path d="M9.2 9a3 3 0 015.6 1.5c0 2-2.8 2.4-2.8 4.3" /><circle cx="12" cy="18.3" r=".6" fill="currentColor" /></svg>
  ),
  History: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M3.5 12a8.5 8.5 0 102.5-6M3.5 4v4h4" /><path d="M12 8v4.5l3 2" /></svg>
  ),
  Pencil: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 20h4L19 9l-4-4L4 16v4z" /><path d="M13.5 6.5l4 4" /></svg>
  ),
  Arrow: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M5 12h14M13 6l6 6-6 6" /></svg>
  ),
  Back: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M19 12H5M11 6l-6 6 6 6" /></svg>
  ),
  Alert: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 3.5l9.5 16.5h-19L12 3.5z" /><path d="M12 10v4" /><circle cx="12" cy="17" r=".6" fill="currentColor" /></svg>
  ),
  Book: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M4 5.5A2.5 2.5 0 016.5 3H20v15H6.5A2.5 2.5 0 004 20.5v-15z" /><path d="M4 20.5A2.5 2.5 0 006.5 23H20v-5" /></svg>
  ),
  Sparkle: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="currentColor" aria-hidden><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7L12 2z" /></svg>
  ),
  Lock: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" aria-hidden><rect x="5" y="10.5" width="14" height="10" rx="2.5" /><path d="M8 10.5V8a4 4 0 018 0v2.5" /></svg>
  ),
  Download: ({ className }: IconProps) => (
    <svg viewBox="0 0 24 24" className={className ?? base} fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d="M12 4v11M7 10.5l5 5 5-5M5 20h14" /></svg>
  ),
};

export function Ring({ value, size = 64, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={label ?? `${Math.round(v * 100)}% done`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={7} className="fill-none stroke-sand-200 dark:stroke-night-600" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={7}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v)}
          className="fill-none stroke-leaf-500 transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <span className="absolute text-sm font-bold tabular-nums">{Math.round(v * 100)}%</span>
    </div>
  );
}

export function Bar({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`h-2 w-full overflow-hidden rounded-full bg-sand-200 dark:bg-night-600 ${className}`}>
      <div className="h-full rounded-full bg-leaf-500 transition-[width] duration-500" style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function TopBar({ title, back = "/", right }: { title: string; back?: string | null; right?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-sand-200/80 bg-sand-100/85 backdrop-blur dark:border-night-700 dark:bg-night-900/85">
      <div className="mx-auto flex h-14 max-w-3xl items-center gap-2 px-4">
        {back !== null && (
          <Link href={back} className="focus-ring -ml-2 grid h-10 w-10 place-items-center rounded-full hover:bg-sand-200 dark:hover:bg-night-700" aria-label="Back">
            <Icon.Back />
          </Link>
        )}
        <h1 className="flex-1 truncate text-[17px] font-semibold">{title}</h1>
        {right}
      </div>
    </header>
  );
}

export function Toast({ message, tone = "ok" }: { message: string | null; tone?: "ok" | "error" }) {
  if (!message) return null;
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-28 z-40 flex justify-center px-4">
      <div className={`animate-rise rounded-full px-4 py-2 text-sm font-semibold shadow-lift ${tone === "ok" ? "bg-ink text-white dark:bg-sand-100 dark:text-night-900" : "bg-clay-600 text-white"}`}>
        {message}
      </div>
    </div>
  );
}

export function useToast(): [string | null, (m: string, tone?: "ok" | "error") => void, "ok" | "error"] {
  const [msg, setMsg] = useState<string | null>(null);
  const [tone, setTone] = useState<"ok" | "error">("ok");
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(() => setMsg(null), 1800);
    return () => clearTimeout(t);
  }, [msg]);
  return [msg, (m, tn = "ok") => { setTone(tn); setMsg(m); }, tone];
}

const COLORS = ["#2a8a70", "#f2b53a", "#c4553b", "#5fbfa4", "#1f6f5c"];

export function Burst({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div aria-hidden className="pointer-events-none fixed inset-x-0 top-20 z-50 flex justify-center">
      <div className="relative h-0 w-0">
        {Array.from({ length: 22 }).map((_, i) => (
          <span
            key={i}
            className="absolute block h-2.5 w-1.5 animate-confetti rounded-sm"
            style={{
              left: `${Math.cos((i / 22) * Math.PI * 2) * (40 + (i % 5) * 18)}px`,
              top: `${Math.sin((i / 22) * Math.PI * 2) * 24}px`,
              background: COLORS[i % COLORS.length],
              animationDelay: `${(i % 6) * 40}ms`,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function Spinner() {
  return <div className="mx-auto h-8 w-8 animate-spin rounded-full border-[3px] border-sand-300 border-t-leaf-500" aria-label="Loading" />;
}
