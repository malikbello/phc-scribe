"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, Icon, Ring, Spinner } from "@/components/ui";
import { api, post } from "@/lib/client";
import { remainingMinutes } from "@/lib/assign";
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

export default function Home() {
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/api/me").then(setMe).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="p-6 text-clay-600">{error}</p>;
  if (!me) return <div className="py-24"><Spinner /></div>;

  const first = me.reviewer.name.split(" ")[0];
  const clinical = me.reviewer.role !== "annotator";
  const reviewLeft = me.review.total - me.review.done;

  return (
    <main className="mx-auto max-w-3xl px-4 pb-16 pt-8">
      <div className="flex items-start justify-between gap-4">
        <div className="animate-rise">
          <p className="muted text-sm font-medium">{greeting()},</p>
          <h1 className="text-[30px] font-bold leading-tight">{first}</h1>
          <p className="muted mt-1">Thank you for helping. Every item you finish makes the benchmark stronger.</p>
        </div>
        <div className="flex items-center gap-1">
          {me.reviewer.role === "admin" && (
            <Link href="/admin" className="btn-ghost min-h-[40px] px-3 text-sm">Admin</Link>
          )}
          <button
            className="btn-ghost min-h-[40px] px-3 text-sm"
            onClick={async () => { await post("/api/logout", {}); window.location.href = "/login"; }}
          >
            Sign out
          </button>
        </div>
      </div>

      <section className="mt-8 space-y-4">
        {clinical && (
          <Link href="/review" className="card focus-ring group block p-5 transition hover:shadow-lift sm:p-6">
            <div className="flex items-center gap-5">
              <Ring value={me.review.done / me.review.total} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-bold uppercase tracking-wider text-leaf-600 dark:text-leaf-500">Clinical sign-off</p>
                <h2 className="mt-0.5 text-xl font-bold">Review the danger-sign rules</h2>
                <p className="muted mt-1 text-sm">
                  {reviewLeft === 0 ? "All done. Thank you!" : `${reviewLeft} quick taps left · about ${Math.max(5, Math.round(reviewLeft * 0.6))} min`}
                </p>
              </div>
              <Icon.Arrow className="h-6 w-6 text-ink-faint transition group-hover:translate-x-1" />
            </div>
          </Link>
        )}

        {me.queues.map((q) => {
          const mineTotal = q.mineDone + q.mineAvailable;
          const mins = remainingMinutes(q.mineAvailable, q.avgMs);
          return (
            <Link key={q.id} href={`/label/${q.id}`} className="card focus-ring group block p-5 transition hover:shadow-lift sm:p-6">
              <div className="flex items-center gap-5">
                <Ring value={mineTotal ? q.mineDone / mineTotal : 1} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-bold uppercase tracking-wider text-sun-600">Labelling</p>
                  <h2 className="mt-0.5 truncate text-xl font-bold">{q.title}</h2>
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
                <Icon.Arrow className="h-6 w-6 text-ink-faint transition group-hover:translate-x-1" />
              </div>
            </Link>
          );
        })}

        {me.queues.length === 0 && (
          <div className="card p-6 text-center">
            <p className="font-semibold">No labelling sets yet</p>
            <p className="muted mt-1 text-sm">Malik will add them soon. You'll see them here.</p>
          </div>
        )}
      </section>

      <p className="faint mt-10 flex items-center justify-center gap-2 text-xs">
        <Icon.Lock className="h-4 w-4" /> Items are confidential. Please don't screenshot or share them.
      </p>
    </main>
  );
}
