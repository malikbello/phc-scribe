"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bar, Burst, Icon, Spinner, Toast, TopBar, useToast } from "@/components/ui";
import { api, post } from "@/lib/client";
import { CONCEPTS, CONCEPT_BY_ID } from "@/lib/content";
import type { ClientItem, QueueProgress } from "@/lib/repo";
import { evidenceLongEnough, type Assertion, type Finding, type SkipReason } from "@/lib/schema";
import { evidenceFor, tap, tokenize, type Range } from "@/lib/spans";

const ASSERTIONS: { id: Assertion; label: string; hint: string; key: string; cls: string }[] = [
  { id: "present", label: "Present", hint: "has it now", key: "1", cls: "bg-clay-500 text-white shadow-glow-coral hover:brightness-110" },
  { id: "absent", label: "Absent", hint: "denied / no", key: "2", cls: "bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950 shadow-glow hover:brightness-110" },
  { id: "possible", label: "Possible", hint: "unsure / maybe", key: "3", cls: "bg-sun-400 text-night-950 shadow-[0_0_24px_-6px_rgba(255,197,66,.6)] hover:brightness-110" },
  { id: "historical", label: "Past pregnancy", hint: "not now", key: "4", cls: "bg-white/10 text-sand-100 ring-1 ring-white/15 hover:bg-white/15" },
];

const SKIPS: { id: SkipReason; label: string }[] = [
  { id: "not_pregnancy_related", label: "Not about pregnancy" },
  { id: "unintelligible", label: "Can't understand it" },
  { id: "not_patient_report", label: "General question, not her own symptoms" },
  { id: "duplicate", label: "Duplicate" },
  { id: "other", label: "Other (add a note)" },
];

const ASSERT_STYLE: Record<Assertion, string> = {
  present: "border-clay-400/60 bg-clay-500/15 text-clay-100 shadow-glow-coral",
  absent: "border-leaf-400/50 bg-leaf-400/10 text-leaf-100",
  possible: "border-sun-400/60 bg-sun-400/10 text-sun-100",
  historical: "border-white/15 bg-white/[.05] text-sand-200",
};

export default function LabelPage() {
  const { queueId } = useParams<{ queueId: string }>();
  const [item, setItem] = useState<ClientItem | null | undefined>(undefined);
  const [progress, setProgress] = useState<QueueProgress | null>(null);
  const [range, setRange] = useState<Range>(null);
  const [concept, setConcept] = useState<string | null>(null);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [note, setNote] = useState("");
  const [search, setSearch] = useState("");
  const [skipOpen, setSkipOpen] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [history, setHistory] = useState<string[]>([]);
  const [session, setSession] = useState(0);
  const [burst, setBurst] = useState(false);
  const [toast, showToast, tone] = useToast();
  const started = useRef(Date.now());

  const tokens = useMemo(() => (item ? tokenize(item.transcript) : []), [item]);
  const evidence = item ? evidenceFor(item.transcript, tokens, range) : "";
  const usedTokens = useMemo(() => {
    const used = new Set<number>();
    if (!item) return used;
    for (const f of findings) {
      const start = item.transcript.indexOf(f.evidence.text);
      if (start < 0) continue;
      const end = start + f.evidence.text.length;
      tokens.forEach((t, i) => { if (t.start < end && t.end > start) used.add(i); });
    }
    return used;
  }, [item, tokens, findings]);

  const refreshProgress = useCallback(async () => {
    const me = await api<{ queues: QueueProgress[] }>("/api/me");
    setProgress(me.queues.find((q) => q.id === queueId) ?? null);
    const h = await api<{ itemIds: string[] }>(`/api/queues/${queueId}/history`);
    setHistory(h.itemIds);
  }, [queueId]);

  const show = useCallback((it: ClientItem | null) => {
    setItem(it);
    setRange(null);
    setConcept(null);
    setSearch("");
    setSkipOpen(false);
    setFindings(it?.mine?.findings ?? []);
    setNote(it?.mine?.note ?? "");
    started.current = Date.now();
    window.scrollTo({ top: 0 });
  }, []);

  const loadNext = useCallback(async () => {
    const { item: it } = await api<{ item: ClientItem | null }>(`/api/queues/${queueId}/next`);
    show(it);
  }, [queueId, show]);

  useEffect(() => {
    loadNext().catch((e) => showToast(e.message, "error"));
    refreshProgress().catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queueId]);

  function addFinding(a: Assertion) {
    if (!evidence) return showToast("First tap the words that show it", "error");
    if (!evidenceLongEnough(evidence)) return showToast("Select a few more words", "error");
    if (!concept) return showToast("Now pick what it is", "error");
    if (findings.some((f) => f.concept === concept && f.assertion === a)) return showToast("Already added", "error");
    setFindings((fs) => [...fs, { concept, assertion: a, evidence: { text: evidence } }]);
    setRange(null);
    setConcept(null);
    setSearch("");
  }

  async function save(status: "labelled" | "skip", skipReason?: SkipReason) {
    if (!item || saving) return;
    if (status === "skip" && skipReason === "other" && !note.trim()) {
      setSkipOpen(false);
      return showToast("Add a short note for 'Other'", "error");
    }
    setSaving(true);
    try {
      await post(`/api/queues/${queueId}/labels`, {
        itemId: item.itemId,
        status,
        skipReason,
        findings: status === "skip" ? [] : findings,
        note: note.trim() || undefined,
        elapsedMs: Date.now() - started.current,
      });
      const wasNew = !item.mine;
      if (wasNew) {
        const n = session + 1;
        setSession(n);
        if (n % 10 === 0) {
          setBurst(true);
          setTimeout(() => setBurst(false), 1300);
          showToast(`${n} done this session. Brilliant!`);
        } else showToast("Saved");
      } else showToast("Updated");
      await loadNext();
      refreshProgress().catch(() => undefined);
    } catch (e) {
      showToast(e instanceof Error ? e.message : "Couldn't save", "error");
    } finally {
      setSaving(false);
    }
  }

  async function openPrevious() {
    const idx = item?.mine ? history.indexOf(item.itemId) - 1 : history.length - 1;
    const id = history[idx];
    if (!id) return showToast("Nothing earlier", "error");
    const { item: it } = await api<{ item: ClientItem }>(`/api/queues/${queueId}/items/${encodeURIComponent(id)}`);
    show(it);
  }

  // Keyboard shortcuts on desktop: 1-4 assertions, Ctrl/Cmd+Enter save.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (t.tagName === "INPUT" || t.tagName === "TEXTAREA") return;
      const a = ASSERTIONS.find((x) => x.key === e.key);
      if (a) { e.preventDefault(); addFinding(a.id); }
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save("labelled"); }
      if (e.key === "Escape") { setRange(null); setConcept(null); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const filtered = CONCEPTS.filter((c) => !search || c.label.toLowerCase().includes(search.toLowerCase()));
  const danger = filtered.filter((c) => c.danger);
  const other = filtered.filter((c) => !c.danger);
  const mineTotal = progress ? progress.mineDone + progress.mineAvailable : 0;

  if (item === undefined) return (<><TopBar title="Labelling" /><div className="py-24"><Spinner /></div></>);

  if (item === null) {
    return (
      <>
        <TopBar title={progress?.title ?? "Labelling"} />
        <Burst show />
        <main className="mx-auto max-w-xl px-4 pt-16 text-center">
          <div className="card animate-pop p-8">
            <Icon.Sparkle className="mx-auto h-10 w-10 text-sun-400" />
            <h2 className="mt-3 text-2xl font-bold">All done here. Ẹ ṣé o!</h2>
            <p className="muted mt-2">
              {progress ? `You labelled ${progress.mineDone} items. ` : ""}Nothing else is waiting for you in this set right now.
            </p>
            <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
              {history.length > 0 && <button className="btn-ghost" onClick={openPrevious}><Icon.History /> Review my last item</button>}
              <Link href="/" className="btn-primary">Back home</Link>
            </div>
          </div>
        </main>
      </>
    );
  }

  const revisiting = Boolean(item.mine);

  return (
    <>
      <TopBar
        title={progress?.title ?? "Labelling"}
        right={
          <div className="flex items-center gap-1">
            <button className="focus-ring grid h-10 w-10 place-items-center rounded-full hover:bg-sand-200 dark:hover:bg-white/[.08]" onClick={openPrevious} aria-label="Previous item" title="Previous item">
              <Icon.History />
            </button>
            <button className="focus-ring grid h-10 w-10 place-items-center rounded-full hover:bg-sand-200 dark:hover:bg-white/[.08]" onClick={() => setGuideOpen(true)} aria-label="How to label" title="How to label">
              <Icon.Book />
            </button>
          </div>
        }
      />
      <Burst show={burst} />
      <main className="mx-auto max-w-3xl px-4 pb-40 pt-3">
        {progress && (
          <div className="mb-3 flex items-center gap-3">
            <Bar value={mineTotal ? progress.mineDone / mineTotal : 0} />
            <span className="muted shrink-0 text-xs font-medium tabular-nums">{progress.mineDone}/{mineTotal}</span>
          </div>
        )}

        {revisiting && (
          <p className="mb-3 rounded-2xl bg-sun-400/10 px-4 py-2 text-sm font-medium text-sun-100 ring-1 ring-sun-400/30">
            Editing an item you already labelled. Saving updates it.
          </p>
        )}

        <section className="card p-5 sm:p-6" aria-label="Item text">
          <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider">
            <span className="rounded-full bg-white/[.07] px-2.5 py-1 text-sand-200 ring-1 ring-white/10">{langName(item.language)}</span>
            {item.double && <span className="rounded-full bg-cyan-400/10 px-2.5 py-1 text-cyan-200 ring-1 ring-cyan-300/30">Agreement check</span>}
          </div>
          <p className="select-none text-[21px] leading-[1.75] sm:text-[23px]" lang={item.language}>
            {tokens.map((t, i) => {
              const inRange = range && i >= range.from && i <= range.to;
              const used = usedTokens.has(i);
              return (
                <span key={i}>
                  <button
                    type="button"
                    onClick={() => setRange((r) => tap(r, i))}
                    className={`rounded-lg px-0.5 transition ${inRange ? "bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950 shadow-glow" : used ? "underline decoration-leaf-400 decoration-2 underline-offset-4" : "hover:bg-sand-200 dark:hover:bg-white/[.08]"}`}
                  >
                    {t.text}
                  </button>{" "}
                </span>
              );
            })}
          </p>
          <p className="faint mt-3 text-xs">Tap a word. Tap another to include everything between. Tap an end to start again.</p>
        </section>

        <section className="card mt-3 p-4 sm:p-5" aria-label="Add a finding">
          <div className="flex items-center gap-2">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gradient-to-br from-leaf-400 to-cyan-400 text-xs font-bold text-night-950 shadow-glow">1</span>
            {evidence ? (
              <p className="min-w-0 flex-1 truncate font-semibold">“{evidence}”</p>
            ) : (
              <p className="muted flex-1">Tap the words that show a finding</p>
            )}
            {evidence && <button className="btn-ghost min-h-[36px] px-3 text-sm" onClick={() => setRange(null)}>Clear</button>}
          </div>

          <div className="mt-4 flex items-center gap-2">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gradient-to-br from-leaf-400 to-cyan-400 text-xs font-bold text-night-950 shadow-glow">2</span>
            <p className="muted flex-1">{concept ? <span className="font-semibold text-ink dark:text-sand-100">{CONCEPT_BY_ID.get(concept)?.label}</span> : "What is it?"}</p>
            <input className="input w-36 py-2 text-sm sm:w-48" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} aria-label="Search findings" />
          </div>
          <ChipGroup title="Danger signs" items={danger} value={concept} onPick={setConcept} danger />
          <ChipGroup title="Other findings" items={other} value={concept} onPick={setConcept} />

          <div className="mt-4 flex items-center gap-2">
            <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-gradient-to-br from-leaf-400 to-cyan-400 text-xs font-bold text-night-950 shadow-glow">3</span>
            <p className="muted">Is it…</p>
          </div>
          <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {ASSERTIONS.map((a) => (
              <button key={a.id} className={`btn focus-ring flex-col gap-0 py-2 leading-tight ${a.cls}`} disabled={!evidence || !concept} onClick={() => addFinding(a.id)}>
                <span>{a.label}</span>
                <span className="text-[11px] font-medium opacity-80">{a.hint}</span>
              </button>
            ))}
          </div>
        </section>

        <section className="mt-3" aria-label="Findings for this item">
          {findings.length === 0 ? (
            <p className="muted px-1 text-sm">No findings yet. If there's nothing to record, just tap <b>Nothing to record</b>.</p>
          ) : (
            <ul className="space-y-2">
              {findings.map((f, i) => {
                const c = CONCEPT_BY_ID.get(f.concept);
                return (
                  <li key={`${f.concept}-${f.assertion}`} className={`flex animate-pop items-center gap-3 rounded-2xl border-2 px-4 py-3 ${ASSERT_STYLE[f.assertion]}`}>
                    {c?.danger && <Icon.Alert className="h-5 w-5 text-clay-400" />}
                    <div className="min-w-0 flex-1">
                      <p className="font-semibold">{c?.label} · <span className="capitalize">{f.assertion === "historical" ? "past pregnancy" : f.assertion}</span></p>
                      <p className="truncate text-sm opacity-80">“{f.evidence.text}”</p>
                    </div>
                    <button className="grid h-9 w-9 place-items-center rounded-full hover:bg-black/5" onClick={() => setFindings((fs) => fs.filter((_, j) => j !== i))} aria-label={`Remove ${c?.label}`}>
                      <Icon.X />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
          <input className="input mt-3 text-sm" placeholder="Note (optional): anything unclear?" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
        </section>

        {item.hints.length > 0 && (
          <section className="mt-3 rounded-2xl border border-dashed border-sand-300 p-3 dark:border-white/10">
            <p className="faint mb-2 text-xs font-semibold uppercase tracking-wide">Suggestions (check them against the text)</p>
            <div className="flex flex-wrap gap-2">
              {item.hints.map((h, i) => (
                <button
                  key={i}
                  className="chip border-white/10 bg-white/[.04] hover:border-leaf-400/50"
                  onClick={() => h.evidence?.text && !findings.some((f) => f.concept === h.concept && f.assertion === h.assertion) && setFindings((fs) => [...fs, { concept: h.concept, assertion: h.assertion, evidence: { text: h.evidence!.text } }])}
                >
                  + {CONCEPT_BY_ID.get(h.concept)?.label} · {h.assertion}
                </button>
              ))}
            </div>
          </section>
        )}
      </main>

      <div className="fixed inset-x-0 bottom-0 z-30 border-t border-white/[.06] bg-night-950/70 backdrop-blur-xl" style={{ paddingBottom: "env(safe-area-inset-bottom)" }}>
        <div className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-3">
          <div className="relative">
            <button className="btn-ghost" onClick={() => setSkipOpen((o) => !o)} aria-expanded={skipOpen}>Skip</button>
            {skipOpen && (
              <div className="card absolute bottom-14 left-0 w-72 animate-pop bg-night-800/90 p-2">
                {SKIPS.map((s) => (
                  <button key={s.id} className="block w-full rounded-xl px-3 py-2.5 text-left text-[15px] hover:bg-white/[.08]" onClick={() => save("skip", s.id)}>
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <button className="btn-primary flex-1 text-base" disabled={saving} onClick={() => save("labelled")}>
            {saving ? "Saving…" : findings.length ? `Save ${findings.length} & next` : "Nothing to record"} <Icon.Arrow />
          </button>
        </div>
      </div>

      {guideOpen && <Guide onClose={() => setGuideOpen(false)} />}
      <Toast message={toast} tone={tone} />
    </>
  );
}

function ChipGroup({ title, items, value, onPick, danger = false }: { title: string; items: typeof CONCEPTS; value: string | null; onPick: (id: string) => void; danger?: boolean }) {
  if (!items.length) return null;
  return (
    <div className="mt-3">
      <p className={`mb-2 text-xs font-bold uppercase tracking-wider ${danger ? "text-clay-400" : "faint"}`}>{title}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((c) => {
          const on = value === c.id;
          const cls = on
            ? danger
              ? "border-clay-400 bg-clay-500 text-white shadow-glow-coral"
              : "border-transparent bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950 shadow-glow"
            : danger
              ? "border-clay-400/30 bg-clay-500/10 text-clay-100 hover:border-clay-400/70"
              : "border-white/10 bg-white/[.04] text-sand-100 hover:border-leaf-400/50";
          return (
            <button key={c.id} className={`chip focus-ring ${cls}`} onClick={() => onPick(c.id)} aria-pressed={on} title={c.definition}>
              {c.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function Guide({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4" onClick={onClose} role="dialog" aria-modal aria-label="How to label">
      <div className="card max-h-[85dvh] w-full max-w-lg animate-rise overflow-y-auto rounded-b-none p-6 sm:rounded-3xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-bold">The five rules that matter</h2>
          <button className="grid h-9 w-9 place-items-center rounded-full hover:bg-sand-200 dark:hover:bg-white/[.08]" onClick={onClose} aria-label="Close"><Icon.X /></button>
        </div>
        <ol className="mt-4 list-decimal space-y-3 pl-5 text-[15px] leading-relaxed">
          <li><b>Record what is said, not what you'd diagnose.</b> "Headache and BP 150/100" is <i>Headache</i>, not pre-eclampsia.</li>
          <li><b>Only the woman herself.</b> Her child's or husband's symptoms are left out.</li>
          <li><b>Include the cue</b> for absent, possible and past: select "no bleeding", not just "bleeding".</li>
          <li><b>Severe only if the words say so</b> (severe, very bad, persistent, "gidigidi"). Otherwise pick the mild finding.</li>
          <li><b>When torn, choose what a cautious clinician would act on.</b> Use <i>Possible</i> rather than leaving a danger sign out.</li>
        </ol>
        <p className="muted mt-4 text-sm">Past pregnancy and now in one sentence? Add two findings: <i>Past pregnancy</i> and <i>Absent</i>. About a minute per item is normal.</p>
        <p className="faint mt-3 text-xs">Keyboard: 1–4 choose the answer · Ctrl+Enter saves · Esc clears.</p>
      </div>
    </div>
  );
}

function langName(code: string): string {
  return ({ en: "English", yo: "Yorùbá", pcm: "Pidgin", ha: "Hausa", ig: "Igbo" } as Record<string, string>)[code] ?? code;
}
