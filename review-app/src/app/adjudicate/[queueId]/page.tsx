"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Burst, Icon, Spinner, Toast, TopBar, useToast } from "@/components/ui";
import { api, post } from "@/lib/client";
import { CONCEPT_BY_ID } from "@/lib/content";
import type { PendingItem } from "@/lib/repo";
import type { Finding } from "@/lib/schema";

// The clinician settles labelling disagreements that need clinical judgement. Answers are
// anonymised (A, B, ...) so the decision is about the words, not who labelled them.

const REASONS = [
  "Matches the guide",
  "A danger sign was missed",
  "Not the speaker's own health",
  "Wrong present / absent / possible",
  "General talk: nothing to record",
  "Can't be understood",
];

const ASSERT: Record<Finding["assertion"], string> = { present: "present", absent: "absent", possible: "possible", historical: "past pregnancy" };
const fkey = (f: Finding) => `${f.concept}|${f.assertion}`;

export default function AdjudicatePage() {
  const { queueId } = useParams<{ queueId: string }>();
  const [item, setItem] = useState<PendingItem | null | undefined>(undefined);
  const [chosen, setChosen] = useState<string | null>(null); // answer name, or "custom"
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [unlabellable, setUnlabellable] = useState(false);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [settled, setSettled] = useState(0);
  const [burst, setBurst] = useState(false);
  const [toast, showToast, tone] = useToast();

  const load = useCallback(async (after?: string) => {
    const q = after ? `?after=${encodeURIComponent(after)}` : "";
    const { item: it } = await api<{ item: PendingItem | null }>(`/api/adjudicate/${queueId}${q}`);
    setItem(it);
    setChosen(null);
    setPicked(new Set());
    setUnlabellable(false);
    setReason("");
    window.scrollTo({ top: 0 });
  }, [queueId]);

  useEffect(() => { load().catch((e) => showToast(e.message, "error")); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [queueId]);

  // Every finding any labeller gave, once, for the "neither is fully right" editor.
  const union = useMemo(() => {
    const m = new Map<string, Finding>();
    for (const a of item?.answers ?? []) for (const f of a.findings) if (!m.has(fkey(f))) m.set(fkey(f), f);
    return [...m.values()];
  }, [item]);

  if (item === undefined) return (<><TopBar title="Settle disagreements" /><div className="py-24"><Spinner /></div></>);
  if (item === null) {
    return (
      <>
        <TopBar title="Settle disagreements" />
        <main className="mx-auto max-w-xl px-4 py-16 text-center">
          <div className="card p-8">
            <Icon.Check className="mx-auto h-10 w-10 text-leaf-400" />
            <h2 className="mt-3 text-2xl font-bold">Nothing to settle. Ẹ ṣé!</h2>
            <p className="muted mt-2">{settled ? `You settled ${settled} this time. ` : ""}New disagreements will appear on your home screen.</p>
            <Link href="/" className="btn-primary mt-6">Back home</Link>
          </div>
        </main>
      </>
    );
  }

  async function save() {
    if (!item || !chosen) return showToast("Choose an answer first", "error");
    if (reason.trim().length < 3) return showToast("Add a short reason (tap one above)", "error");
    let body;
    if (chosen === "custom") {
      body = unlabellable
        ? { status: "skip", skipReason: "unintelligible", findings: [] }
        : { status: "labelled", findings: union.filter((f) => picked.has(fkey(f))) };
    } else {
      const a = item.answers.find((x) => x.name === chosen)!;
      body = { status: a.status, skipReason: a.skip_reason, findings: a.findings };
    }
    setSaving(true);
    try {
      await post(`/api/adjudicate/${queueId}`, { itemId: item.itemId, reason: reason.trim(), ...body });
      const n = settled + 1;
      setSettled(n);
      if (n % 10 === 0) { setBurst(true); setTimeout(() => setBurst(false), 1300); }
      showToast(n % 10 === 0 ? `${n} settled. Brilliant!` : "Decided");
      await load(item.itemId);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Couldn't save", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <TopBar title="Settle disagreements" />
      <Burst show={burst} />
      <main className="mx-auto max-w-3xl px-4 pb-40 pt-3">
        <p className="mb-3 rounded-2xl bg-sun-400/10 px-4 py-2 text-sm text-sun-100 ring-1 ring-sun-400/30">
          Labellers disagreed here (<b>{item.why}</b>). Pick the right answer, using the same rules as labelling. You won&apos;t see who gave which.
        </p>

        <section className="card p-5" aria-label="Item text">
          <p className="faint mb-2 text-xs font-semibold uppercase tracking-wider">{({ yo: "Yorùbá", pcm: "Pidgin", en: "English" } as Record<string, string>)[item.language] ?? item.language}{item.source === "wazobia" ? " · real speech" : ""}</p>
          <p className="text-[19px] leading-[1.7] sm:text-[22px]" lang={item.language}>{item.transcript}</p>
        </section>

        <div className="mt-3 space-y-2">
          {item.answers.map((a) => (
            <button key={a.name} onClick={() => setChosen(a.name)} aria-pressed={chosen === a.name}
              className={`card focus-ring block w-full p-4 text-left transition ${chosen === a.name ? "ring-2 ring-leaf-400" : ""}`}>
              <div className="flex items-center justify-between">
                <span className="font-bold">Answer {a.name}</span>
                <span className="muted text-xs">{a.count} {a.count === 1 ? "person" : "people"}</span>
              </div>
              <AnswerBody status={a.status} skip={a.skip_reason} findings={a.findings} />
            </button>
          ))}
          <button onClick={() => setChosen("custom")} aria-pressed={chosen === "custom"}
            className={`card focus-ring block w-full p-4 text-left ${chosen === "custom" ? "ring-2 ring-leaf-400" : ""}`}>
            <span className="font-bold">None is fully right</span>
            <span className="muted block text-sm">Choose which findings are correct.</span>
          </button>
        </div>

        {chosen === "custom" && (
          <section className="card mt-3 space-y-2 p-4">
            {union.map((f) => (
              <label key={fkey(f)} className="flex items-start gap-3 rounded-xl p-2 hover:bg-white/[.05]">
                <input type="checkbox" className="mt-1 h-5 w-5" disabled={unlabellable} checked={picked.has(fkey(f))}
                  onChange={(e) => setPicked((p) => { const n = new Set(p); if (e.target.checked) n.add(fkey(f)); else n.delete(fkey(f)); return n; })} />
                <span><b>{CONCEPT_BY_ID.get(f.concept)?.label ?? f.concept}</b> · {ASSERT[f.assertion]}<span className="muted block text-sm">“{f.evidence.text}”</span></span>
              </label>
            ))}
            <label className="flex items-center gap-3 rounded-xl p-2 hover:bg-white/[.05]">
              <input type="checkbox" className="h-5 w-5" checked={unlabellable} onChange={(e) => setUnlabellable(e.target.checked)} />
              <span>Can&apos;t be labelled (garbled, cut off, other language)</span>
            </label>
            <p className="faint text-xs">{unlabellable ? "Will be left out of the benchmark, and counted in the report." : picked.size ? `${picked.size} finding${picked.size > 1 ? "s" : ""} will be the answer.` : "Nothing ticked = Nothing to record."}</p>
          </section>
        )}

        {chosen && (
          <section className="mt-3">
            <p className="mb-2 text-sm font-semibold">Why? (tap one or type)</p>
            <div className="flex flex-wrap gap-2">
              {REASONS.map((r) => (
                <button key={r} className={`chip focus-ring ${reason === r ? "border-transparent bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950" : "border-white/10 bg-white/[.04]"}`} onClick={() => setReason(r)}>{r}</button>
              ))}
            </div>
            <input className="input mt-2 text-sm" placeholder="Or write a short reason" value={REASONS.includes(reason) ? "" : reason} onChange={(e) => setReason(e.target.value)} maxLength={500} />
          </section>
        )}
      </main>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/[.06] bg-night-950/70 backdrop-blur-xl" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        <div className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-3">
          <button className="btn-ghost" onClick={() => load(item.itemId)}>Later</button>
          <button className="btn-primary flex-1 text-base" disabled={saving || !chosen} onClick={save}>
            {saving ? "Saving…" : "Decide & next"} <Icon.Arrow />
          </button>
        </div>
      </div>
      <Toast message={toast} tone={tone} />
    </>
  );
}

function AnswerBody({ status, skip, findings }: { status: string; skip?: string; findings: Finding[] }) {
  if (status === "skip") return <p className="muted mt-1 text-sm">Skipped ({(skip ?? "").replace(/_/g, " ")})</p>;
  if (!findings.length) return <p className="mt-1 text-sm">Nothing to record</p>;
  return (
    <ul className="mt-2 space-y-1.5">
      {findings.map((f) => {
        const c = CONCEPT_BY_ID.get(f.concept);
        return (
          <li key={fkey(f)} className="text-sm">
            {c?.danger && <Icon.Alert className="mr-1 inline h-4 w-4 text-clay-400" />}
            <b>{c?.label ?? f.concept}</b> · {ASSERT[f.assertion]} <span className="muted">“{f.evidence.text}”</span>
          </li>
        );
      })}
    </ul>
  );
}
