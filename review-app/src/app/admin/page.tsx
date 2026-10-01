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
  everyone: boolean;
  total: number;
  doubleTotal: number;
  labelledItems: number;
  complete: number;
  perReviewer: Record<string, number>;
  agreement: {
    items: number;
    pairs: number;
    exact: number | null;
    dangerKappa: number | null;
    pairF1: number | null;
    disagreements: { itemId: string; labels: Label[]; transcript?: string }[];
  };
};
type Stats = { team: Team; queues: QueueStat[]; reviewDone: Record<string, number>; reviewTotal: Record<string, number> };

const fmt = (x: number | null, d = 2) => (x === null ? "–" : x.toFixed(d));

export default function Admin() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [toast, showToast, tone] = useToast();
  async function removeSet(id: string, title: string) {
    if (!window.confirm(`Delete "${title}"? Nobody has labelled it yet, so nothing is lost.`)) return;
    try {
      await api(`/api/admin/queues/${encodeURIComponent(id)}`, { method: "DELETE" });
      showToast("Set deleted");
      load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Delete failed", "error");
    }
  }
  async function setPractice(id: string, everyone: boolean) {
    try {
      await api(`/api/admin/queues/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ everyone }) });
      showToast(everyone ? "Everyone will label every item in this set" : "Back to normal sharing");
      load();
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Update failed", "error");
    }
  }
  const load = useCallback(() => api<Stats>("/api/admin/stats").then(setStats).catch((e) => showToast(e.message, "error")), [showToast]);
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  if (!stats) return (<><TopBar title="Admin" /><div className="py-24"><Spinner /></div></>);
  const name = (id: string) => stats.team.find((t) => t.id === id)?.name ?? id;

  return (
    <>
      <TopBar title="Admin" right={<button className="btn-ghost min-h-[40px] px-3 text-sm" onClick={load}>Refresh</button>} />
      <main className="mx-auto max-w-3xl space-y-6 px-4 pb-20 pt-4">
        <Team onChange={load} notify={showToast} />
        <Upload onDone={() => { showToast("Queue created"); load(); }} onError={(m) => showToast(m, "error")} />

        <section className="card p-5">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-bold">Clinical sign-off</h2>
            <a className="btn-ghost min-h-[40px] px-3 text-sm" href="/api/admin/export?kind=review"><Icon.Download /> Export</a>
          </div>
          <ul className="mt-3 space-y-2">
            {stats.team.filter((t) => (stats.reviewTotal[t.id] ?? 0) > 0).map((t) => (
              <li key={t.id} className="flex items-center gap-3">
                <span className="w-28 truncate text-sm font-medium">{t.name}</span>
                <Bar value={(stats.reviewDone[t.id] ?? 0) / stats.reviewTotal[t.id]} />
                <span className="muted w-14 text-right text-xs tabular-nums">{stats.reviewDone[t.id] ?? 0}/{stats.reviewTotal[t.id]}</span>
              </li>
            ))}
          </ul>
        </section>

        {stats.queues.map((q) => (
          <section key={q.id} className="card p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-bold">{q.title}</h2>
                <p className="muted text-sm">
                  {q.everyone ? `Practice set: everyone labels all ${q.total} items` : `${q.total} items · ${q.doubleTotal} double-labelled`} · {q.complete} complete
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-ghost min-h-[40px] px-3 text-sm" onClick={() => setPractice(q.id, !q.everyone)}>
                  {q.everyone ? "Stop: share items normally" : "Make it a practice set (everyone labels all)"}
                </button>
                {q.labelledItems === 0 && (
                  <button className="btn-ghost min-h-[40px] px-3 text-sm text-clay-400" onClick={() => removeSet(q.id, q.title)}>Delete set</button>
                )}
                <a className="btn-ghost min-h-[40px] px-3 text-sm" href={`/api/admin/export?kind=labels&queue=${encodeURIComponent(q.id)}`}><Icon.Download /> Labels (JSONL)</a>
              </div>
            </div>
            <Bar value={q.total ? q.complete / q.total : 0} className="mt-3" />
            <div className="mt-4 grid grid-cols-3 gap-2 text-center">
              <Metric label="Exact agreement" value={q.agreement.exact === null ? "–" : `${Math.round(q.agreement.exact * 100)}%`} />
              <Metric label="Danger-sign kappa" value={fmt(q.agreement.dangerKappa)} />
              <Metric label="Finding F1" value={fmt(q.agreement.pairF1)} />
            </div>
            <p className="faint mt-1 text-center text-xs">From {q.agreement.items} items labelled by two or more people ({q.agreement.pairs} pairs of labellers) so far.</p>
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
                    <li key={d.itemId} className="rounded-2xl bg-sand-100 p-3 text-sm dark:bg-white/[.06]">
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
    <div className="rounded-2xl bg-sand-100 px-2 py-3 dark:bg-white/[.06]">
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
  const [everyone, setEveryone] = useState(false);
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
      await post("/api/admin/queues", { title, items, doubleShare: share / 100, showHints: hints, everyone });
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
            <input type="range" min={0} max={100} step={5} value={share} onChange={(e) => setShare(Number(e.target.value))} className="mt-2 w-full accent-leaf-600" />
            <span className="faint text-xs">These items get two independent labels, for the agreement statistics. Use 100% for a calibration round.</span>
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={everyone} onChange={(e) => setEveryone(e.target.checked)} className="h-4 w-4 accent-leaf-600" />
            Practice set: everyone labels every item (for calibration; the share above is ignored)
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

type Member = { id: string; name: string; role: "admin" | "clinician" | "pharmacist" | "annotator"; source: "env" | "invite"; createdAt?: string };
const ROLES: { id: Member["role"]; label: string; hint: string }[] = [
  { id: "clinician", label: "Clinician", hint: "sign-off + labelling" },
  { id: "pharmacist", label: "Pharmacist", hint: "medicines check + labelling" },
  { id: "annotator", label: "Annotator", hint: "labelling only" },
  { id: "admin", label: "Admin", hint: "everything" },
];

function Team({ onChange, notify }: { onChange: () => void; notify: (m: string, tone?: "ok" | "error") => void }) {
  const [members, setMembers] = useState<Member[] | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState<Member["role"]>("clinician");
  const [issued, setIssued] = useState<{ name: string; code: string } | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => api<{ reviewers: Member[] }>("/api/admin/reviewers").then((d) => setMembers(d.reviewers)), []);
  useEffect(() => { load().catch((e) => notify(e.message, "error")); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);

  async function invite() {
    setBusy(true);
    try {
      const res = await post<{ reviewer: Member; code: string }>("/api/admin/reviewers", { name: name.trim(), role });
      setIssued({ name: res.reviewer.name, code: res.code });
      setName("");
      await load();
      onChange();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Invite failed", "error");
    } finally {
      setBusy(false);
    }
  }

  async function revoke(id: string) {
    if (confirm !== id) return setConfirm(id);
    try {
      await post("/api/admin/reviewers/revoke", { id });
      setConfirm(null);
      notify("Access revoked");
      await load();
      onChange();
    } catch (e) {
      notify(e instanceof Error ? e.message : "Couldn't revoke", "error");
    }
  }

  return (
    <section className="card p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold tracking-tight">Team</h2>
        <span className="faint text-xs">{members?.length ?? "–"} people</span>
      </div>
      <p className="muted mt-1 text-sm">Invite reviewers without redeploying. Each code is shown once; only a keyed hash is stored. Clinicians do the full sign-off and labelling; pharmacists check the medicines and label; annotators label only.</p>

      <div className="mt-4 grid gap-2 sm:grid-cols-[1fr_auto_auto]">
        <input className="input" placeholder="Full name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} aria-label="Name" />
        <select className="input sm:w-40" value={role} onChange={(e) => setRole(e.target.value as Member["role"])} aria-label="Role">
          {ROLES.map((r) => <option key={r.id} value={r.id} className="bg-night-800">{r.label}</option>)}
        </select>
        <button className="btn-primary" disabled={busy || !name.trim()} onClick={invite}>Invite</button>
      </div>

      {issued && (
        <div className="mt-4 animate-pop rounded-2xl bg-leaf-400/10 p-4 ring-1 ring-leaf-400/30">
          <p className="text-sm font-semibold text-leaf-100">Access code for {issued.name}. Copy it now: it won't be shown again.</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="flex-1 truncate rounded-xl bg-night-950/60 px-3 py-2 font-mono text-base tracking-wide text-sand-50">{issued.code}</code>
            <button
              className="btn-ghost min-h-[40px] px-3 text-sm"
              onClick={async () => { try { await navigator.clipboard.writeText(issued.code); notify("Copied"); } catch { notify("Copy failed: select it manually", "error"); } }}
            >
              Copy
            </button>
          </div>
          <p className="faint mt-2 text-xs">Send it privately (a direct message, not a group). <button className="underline" onClick={() => setIssued(null)}>Done</button></p>
        </div>
      )}

      <ul className="mt-4 divide-y divide-white/[.06]">
        {(members ?? []).map((m) => (
          <li key={m.id} className="flex items-center gap-3 py-2.5">
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-leaf-400/30 to-cyan-400/30 text-sm font-bold ring-1 ring-white/10">
              {m.name.slice(0, 1).toUpperCase()}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{m.name}</p>
              <p className="faint text-xs">{ROLES.find((r) => r.id === m.role)?.label ?? m.role}{m.source === "env" ? " · set in Vercel" : ""}</p>
            </div>
            {m.source === "invite" && (
              <button className={`btn min-h-[36px] rounded-full px-3 text-sm ${confirm === m.id ? "bg-clay-500 text-white" : "bg-white/[.06] text-sand-200 ring-1 ring-white/10 hover:bg-white/10"}`} onClick={() => revoke(m.id)}>
                {confirm === m.id ? "Tap to confirm" : "Revoke"}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
