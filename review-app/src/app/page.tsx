"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { Bar, Icon, Ring, Spinner } from "@/components/ui";
import { remainingMinutes } from "@/lib/assign";
import { api, post } from "@/lib/client";
import { displayName } from "@/lib/names";
import type { QueueProgress } from "@/lib/repo";

type Me = {
  reviewer: { id: string; name: string; role: "admin" | "clinician" | "annotator" };
  queues: QueueProgress[];
  review: { done: number; total: number };
};

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Ẹ kú àárọ̀";
  if (h < 16) return "Ẹ kú ọ̀sán";
  return "Ẹ kú alẹ́";
}

const ROLE: Record<Me["reviewer"]["role"], string> = { admin: "Admin", clinician: "Clinical reviewer", annotator: "Annotator" };

export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/api/me").then(setMe).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="p-6 text-clay-400">{error}</p>;
  if (!me) return <div className="py-32"><Spinner /></div>;

  const first = displayName(me.reviewer.name);
  const clinical = me.reviewer.role !== "annotator";
  const reviewLeft = me.review.total - me.review.done;
  const labelled = me.queues.reduce((n, q) => n + q.mineDone, 0);
  const waiting = me.queues.reduce((n, q) => n + q.mineAvailable, 0);

  return (
    <main className="mx-auto max-w-3xl px-4 pb-16 pt-6">
      <nav className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <Logo size={36} />
          <span className="text-[15px] font-semibold tracking-tight">PHC Scribe <span className="faint font-normal">Review</span></span>
        </div>
        <div className="flex items-center gap-1.5">
          {me.reviewer.role === "admin" && <Link href="/admin" className="btn-ghost min-h-[36px] rounded-full px-3.5 text-sm">Admin</Link>}
          <button
            className="btn-ghost min-h-[36px] rounded-full px-3.5 text-sm"
            onClick={async () => { await post("/api/logout", {}); window.location.href = "/login"; }}
          >
            Sign out
          </button>
        </div>
      </nav>

      <header className="mt-10 animate-rise">
        <p className="eyebrow text-leaf-400">{greeting()} · {ROLE[me.reviewer.role]}</p>
        <h1 className="gradient-text mt-2 text-[40px] font-bold leading-[1.05] tracking-tight sm:text-5xl">{first}</h1>
        <p className="muted mt-3 max-w-md">Every item you finish makes the benchmark stronger, and helps catch danger signs for Nigerian mothers.</p>
      </header>

      <section className="mt-7 grid animate-rise grid-cols-3 gap-2 [animation-delay:80ms]" aria-label="Your progress">
        <Stat value={labelled} label="labelled" />
        <Stat value={waiting} label="waiting" />
        <Stat value={clinical ? `${Math.round((me.review.done / me.review.total) * 100)}%` : "–"} label="sign-off" />
      </section>

      <section className="mt-6 space-y-3">
        {clinical && (
          <Link href="/review" className="card card-hover focus-ring group block animate-rise p-5 [animation-delay:140ms] sm:p-6">
            <div className="flex items-center gap-5">
              <Ring value={me.review.done / me.review.total} />
              <div className="min-w-0 flex-1">
                <p className="eyebrow text-leaf-400">Clinical sign-off</p>
                <h2 className="mt-1 text-xl font-bold tracking-tight">Review the danger-sign rules</h2>
                <p className="muted mt-1 text-sm">
                  {reviewLeft === 0 ? "All done. Thank you!" : `${reviewLeft} quick taps left · about ${Math.max(5, Math.round(reviewLeft * 0.6))} min`}
                </p>
              </div>
              <Icon.Arrow className="h-6 w-6 text-sand-300 transition group-hover:translate-x-1 group-hover:text-leaf-400" />
            </div>
          </Link>
        )}

        {me.queues.map((q, i) => {
          const mineTotal = q.mineDone + q.mineAvailable;
          const mins = remainingMinutes(q.mineAvailable, q.avgMs);
          return (
            <Link
              key={q.id}
              href={`/label/${q.id}`}
              className="card card-hover focus-ring group block animate-rise p-5 sm:p-6"
              style={{ animationDelay: `${200 + i * 60}ms` }}
            >
              <div className="flex items-center gap-5">
                <Ring value={mineTotal ? q.mineDone / mineTotal : 1} />
                <div className="min-w-0 flex-1">
                  <p className="eyebrow text-cyan-300">Labelling</p>
                  <h2 className="mt-1 truncate text-xl font-bold tracking-tight">{q.title}</h2>
                  <p className="muted mt-1 text-sm">
                    {q.mineAvailable === 0
                      ? `You've done ${q.mineDone}. Nothing waiting for you right now.`
                      : `${q.mineDone} done · ${q.mineAvailable} waiting · about ${mins} min`}
                  </p>
                  <div className="mt-3 flex items-center gap-3">
                    <Bar value={q.total ? q.teamComplete / q.total : 0} />
                    <span className="faint shrink-0 text-xs tabular-nums">Team {q.teamComplete}/{q.total}</span>
                  </div>
                </div>
                <Icon.Arrow className="h-6 w-6 text-sand-300 transition group-hover:translate-x-1 group-hover:text-cyan-300" />
              </div>
            </Link>
          );
        })}

        {me.queues.length === 0 && (
          <div className="card p-6 text-center">
            <p className="font-semibold">No labelling sets yet</p>
            <p className="muted mt-1 text-sm">Malik will add them soon. They'll appear here.</p>
          </div>
        )}
      </section>

      <p className="faint mt-12 flex items-center justify-center gap-2 text-xs">
        <Icon.Lock className="h-4 w-4" /> Items are confidential. Please don't screenshot or share them.
      </p>
    </main>
  );
}

function Stat({ value, label }: { value: number | string; label: string }) {
  return (
    <div className="card px-3 py-3 text-center">
      <p className="text-2xl font-bold tabular-nums tracking-tight">{value}</p>
      <p className="eyebrow faint mt-0.5">{label}</p>
    </div>
  );
}
