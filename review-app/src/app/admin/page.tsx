"use client";

import { useCallback, useEffect, useState } from "react";
import { Bar, Icon, Spinner, Toast, TopBar, useToast } from "@/components/ui";
import { api, post } from "@/lib/client";
import { CONCEPT_BY_ID } from "@/lib/content";
import type { Label } from "@/lib/schema";

type Team = { id: string; name: string; role: string }[];
type QueueStat = {
  id: string;
  title: string;
  total: number;
  doubleTotal: number;
  labelledItems: number;
  complete: number;
  perReviewer: Record<string, number>;
  agreement: {
    items: number;
    exact: number | null;
    dangerKappa: number | null;
    pairF1: number | null;
    disagreements: { itemId: string; labels: Label[]; transcript?: string }[];
  };
};
type Stats = { team: Team; queues: QueueStat[]; reviewDone: Record<string, number>; reviewTotal: number };

const fmt = (x: number | null, d = 2) => (x === null ? "–" : x.toFixed(d));

export default function Admin() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [toast, showToast, tone] = useToast();
  const load = useCallback(() => api<Stats>("/api/admin/stats").then(setStats).catch((e) => showToast(e.message, "error")), [showToast]);
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  if (!stats) return (<><TopBar title="Admin" /><div className="py-24"><Spinner /></div></>);
  const name = (id: string) => stats.team.find((t) => t.id === id)?.name ?? id;

  return (
    <>
      <TopBar title="Admin" right={<button className="btn-ghost min-h-[40px] px-3 text-sm" onClick={load}>Refresh</button>} />
      <main className="mx-auto max-w-3xl space-y-6 px-4 pb-20 pt-4">
        <Upload onDone={() => { showToast("Queue created"); load(); }} onError={(m) => showToast(m, "error")} />

        <section className="card p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold">Clinical sign-off</h2>
            <a className="btn-ghost min-h-[40px] px-3 text-sm" href="/api/admin/export?kind=review"><Icon.Download /> Export</a>
          </div>
          <ul className="mt-3 space-y-2">
            {stats.team.filter((t) => t.role !== "annotator").map((t) => (
              <li key={t.id} className="flex items-center gap-3">
                <span className="w-28 truncate text-sm font-medium">{t.name}</span>
                <Bar value={(stats.reviewDone[t.id] ?? 0) / stats.reviewTotal} />
                <span className="muted w-14 text-right text-xs tabular-nums">{stats.reviewDone[t.id] ?? 0}/{stats.reviewTotal}</span>
              </li>
            ))}
          </ul>
        </section>

        {stats.queues.map((q) => (
          <section key={q.id} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">{q.title}</h2>
                <p className="muted text-sm">{q.total} items · {q.doubleTotal} double-labelled · {q.complete} complete</p>
              </div>
              <a className="btn-ghost min-h-[40px] px-3 text-sm" href={`/api/admin/export?kind=labels&queue=${encodeURIComponent(q.id)}`}><Icon.Download /> Labels (JSONL)</a>
            </div>
            <Bar value={q.total ? q.complete / q.total : 0} className="mt-3" />
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <Metric label="Exact agreement" value={q.agreement.exact === null ? "–" : `${Math.round(q.agreement.exact * 100)}%`} />
              <Metric label="Danger-sign kappa" value={fmt(q.agreement.dangerKappa)} />
              <Metric label="Finding F1" value={fmt(q.agreement.pairF1)} />
            </div>
            <p className="faint mt-1 text-center text-xs">From {q.agreement.items} double-labelled items so far.</p>
            <ul className="mt-4 space-y-1.5">
              {Object.entries(q.perReviewer).map(([rid, n]) => (
                <li key={rid} className="flex justify-between text-sm"><span>{name(rid)}</span><span className="tabular-nums">{n}</span></li>
              ))}
            </ul>
            {q.agreement.disagreements.length > 0 && (
              <details className="mt-4">
                <summary className="cursor-pointer text-sm font-semibold">Disagreements to adjudicate ({q.agreement.disagreements.length})</summary>
                <ul className="mt-3 space-y-3">
                  {q.agreement.disagreements.map((d) => (
                    <li key={d.itemId} className="rounded-2xl bg-sand-100 p-3 text-sm dark:bg-night-700">
                      <p className="mb-2 leading-relaxed">{d.transcript}</p>
                      {d.labels.map((l) => (
                        <p key={l.labeller} className="mt-1">
                          <b>{name(l.labeller)}:</b>{" "}
                          {l.status === "skip" ? `skipped (${l.skip_reason})` : l.findings.length ? l.findings.map((f) => `${CONCEPT_BY_ID.get(f.concept)?.label ?? f.concept} ${f.assertion}`).join(", ") : "nothing recorded"}
                        </p>
                      ))}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>
        ))}
      </main>
      <Toast message={toast} tone={tone} />
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-sand-100 px-2 py-3 dark:bg-night-700">
      <p className="text-xl font-bold tabular-nums">{value}</p>
      <p className="faint text-[11px] font-semibold uppercase tracking-wide">{label}</p>
    </div>
  );
}

function Upload({ onDone, onError }: { onDone: () => void; onError: (m: string) => void }) {
  const [title, setTitle] = useState("");
  const [items, setItems] = useState<unknown[] | null>(null);
  const [fileName, setFileName] = useState("");
  const [share, setShare] = useState(20);
  const [hints, setHints] = useState(false);
  const [busy, setBusy] = useState(false);

  async function pick(f: File | undefined) {
    if (!f) return;
    try {
      const rows = (await f.text()).split(/\r?\n/).filter((l) => l.trim()).map((l) => JSON.parse(l));
      setItems(rows);
      setFileName(f.name);
      if (!title) setTitle(f.name.replace(/\.jsonl?$/, "").replace(/[._-]+/g, " "));
    } catch {
      onError("That file isn't valid JSONL");
    }
  }

  async function submit() {
    if (!items) return;
    setBusy(true);
    try {
      await post("/api/admin/queues", { title, items, doubleShare: share / 100, showHints: hints });
      setItems(null);
      setFileName("");
      setTitle("");
      onDone();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card p-5">
      <h2 className="text-lg font-bold">Add a labelling set</h2>
      <p className="muted mt-1 text-sm">Upload a queue file (for example <code>data/private/label_queue.s4.jsonl</code>). Items are stored server-side and only shown to signed-in team members.</p>
      <label className="btn-ghost mt-4 w-full cursor-pointer">
        <input type="file" accept=".jsonl,.json" className="sr-only" onChange={(e) => pick(e.target.files?.[0])} />
        {fileName ? `${fileName} · ${items?.length ?? 0} items` : "Choose queue file"}
      </label>
      {items && (
        <div className="mt-4 space-y-4 animate-rise">
          <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title people will see" maxLength={80} />
          <label className="block text-sm">
            <span className="font-medium">Double-labelled share: {share}%</span>
            <input type="range" min={0} max={50} step={5} value={share} onChange={(e) => setShare(Number(e.target.value))} className="mt-2 w-full accent-leaf-600" />
            <span className="faint text-xs">These items get two independent labels, for the agreement statistics.</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={hints} onChange={(e) => setHints(e.target.checked)} className="h-4 w-4 accent-leaf-600" />
            Show keyword suggestions (leave off for agreement checks)
          </label>
          <button className="btn-primary w-full" disabled={busy || !title.trim()} onClick={submit}>{busy ? "Uploading…" : "Create set"}</button>
        </div>
      )}
    </section>
  );
}
