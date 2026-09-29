"use client";

import Link from "next/link";
import { useEffect, useId, useState } from "react";

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
  const id = useId().replace(/:/g, "");
  const r = (size - 8) / 2;
  const c = 2 * Math.PI * r;
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }} role="img" aria-label={label ?? `${Math.round(v * 100)}% done`}>
      <svg width={size} height={size} className="-rotate-90 drop-shadow-[0_0_10px_rgba(62,230,168,.45)]">
        <defs>
          <linearGradient id={`ring-${id}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#3ee6a8" />
            <stop offset="1" stopColor="#22d3ee" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} strokeWidth={6} className="fill-none stroke-white/10" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - v)}
          stroke={`url(#ring-${id})`}
          className="fill-none transition-[stroke-dashoffset] duration-1000 ease-out"
        />
      </svg>
      <span className="absolute text-sm font-bold tabular-nums tracking-tight">{Math.round(v * 100)}%</span>
    </div>
  );
}

export function Bar({ value, className = "" }: { value: number; className?: string }) {
  const v = Math.max(0, Math.min(1, value));
  return (
    <div className={`h-1.5 w-full overflow-hidden rounded-full bg-white/10 ${className}`}>
      <div
        className="h-full rounded-full bg-gradient-to-r from-leaf-400 to-cyan-400 shadow-[0_0_12px_rgba(62,230,168,.6)] transition-[width] duration-700 ease-out"
        style={{ width: `${v * 100}%` }}
      />
    </div>
  );
}

export function TopBar({ title, back = "/", right }: { title: string; back?: string | null; right?: React.ReactNode }) {
  return (
    <header className="sticky top-0 z-20 border-b border-white/[.06] bg-night-950/55 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-3xl items-center gap-2 px-4">
        {back !== null && (
          <Link href={back} className="focus-ring -ml-2 grid h-10 w-10 place-items-center rounded-full hover:bg-sand-200 dark:hover:bg-white/[.08]" aria-label="Back">
            <Icon.Back />
          </Link>
        )}
        <h1 className="flex-1 truncate text-[17px] font-semibold tracking-tight">{title}</h1>
        {right}
      </div>
    </header>
  );
}

export function Toast({ message, tone = "ok" }: { message: string | null; tone?: "ok" | "error" }) {
  if (!message) return null;
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 bottom-28 z-40 flex justify-center px-4">
      <div className={`animate-rise rounded-full px-4 py-2 text-sm font-semibold shadow-lift ring-1 backdrop-blur-xl ${tone === "ok" ? "bg-leaf-400/15 text-leaf-100 ring-leaf-400/40" : "bg-clay-500/20 text-clay-100 ring-clay-400/50"}`}>
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

const COLORS = ["#3ee6a8", "#22d3ee", "#ffc542", "#ff8591", "#c084fc"];

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
  return <div className="mx-auto h-9 w-9 animate-spin rounded-full border-[3px] border-white/10 border-t-leaf-400 shadow-glow" aria-label="Loading" />;
}
