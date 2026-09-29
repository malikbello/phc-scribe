"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, Burst, Icon, Spinner, Toast, TopBar, useToast } from "@/components/ui";
import { api, post } from "@/lib/client";
import { REVIEW_SECTIONS, REVIEW_TOTAL, type ReviewRow } from "@/lib/content";
import type { StoredReviewAnswer } from "@/lib/schema";

type Answers = Record<string, StoredReviewAnswer>;

export default function ReviewPage() {
  const [answers, setAnswers] = useState<Answers | null>(null);
  const [section, setSection] = useState(0);
  const [onlyOpen, setOnlyOpen] = useState(false);
  const [toast, showToast, tone] = useToast();
  const [burst, setBurst] = useState(false);

  useEffect(() => {
    api<{ answers: Answers }>("/api/review").then((d) => setAnswers(d.answers)).catch((e) => showToast(e.message, "error"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const done = answers ? Object.keys(answers).length : 0;

  async function save(row: ReviewRow, verdict: StoredReviewAnswer["verdict"], note?: string) {
    const prev = answers?.[row.key];
    const optimistic = { key: row.key, verdict, note, at: new Date().toISOString() };
    setAnswers((a) => ({ ...(a ?? {}), [row.key]: optimistic }));
    try {
      const { saved } = await post<{ saved: StoredReviewAnswer }>("/api/review", { key: row.key, verdict, note });
      setAnswers((a) => ({ ...(a ?? {}), [row.key]: saved }));
      const nowDone = Object.keys({ ...(answers ?? {}), [row.key]: saved }).length;
      if (!prev && nowDone === REVIEW_TOTAL) {
        setBurst(true);
        setTimeout(() => setBurst(false), 1400);
      }
    } catch (e) {
      setAnswers((a) => {
        const next = { ...(a ?? {}) };
        if (prev) next[row.key] = prev;
        else delete next[row.key];
        return next;
      });
      showToast(e instanceof Error ? e.message : "Couldn't save", "error");
    }
  }

  if (!answers) return (<><TopBar title="Clinical sign-off" /><div className="py-24"><Spinner /></div></>);

  const sec = REVIEW_SECTIONS[section];
  const rows = onlyOpen ? sec.rows.filter((r) => !answers[r.key]) : sec.rows;
  const secDone = sec.rows.filter((r) => answers[r.key]).length;

  return (
    <>
      <TopBar title="Clinical sign-off" right={<span className="muted text-sm tabular-nums">{done}/{REVIEW_TOTAL}</span>} />
      <Burst show={burst} />
      <main className="mx-auto max-w-3xl px-4 pb-24 pt-4">
        <Bar value={done / REVIEW_TOTAL} />
        <nav className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 pb-1" aria-label="Sections">
          {REVIEW_SECTIONS.map((s, i) => {
            const d = s.rows.filter((r) => answers[r.key]).length;
            const active = i === section;
            return (
              <button
                key={s.id}
                onClick={() => setSection(i)}
                className={`chip focus-ring shrink-0 ${active ? "border-transparent bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950 shadow-glow" : "border-white/10 bg-white/[.04] text-sand-100 hover:border-leaf-400/40"}`}
                aria-current={active}
              >
                {d === s.rows.length && <Icon.Check className="h-4 w-4" />}
                {s.title}
                <span className={`text-xs tabular-nums ${active ? "opacity-80" : "faint"}`}>{d}/{s.rows.length}</span>
              </button>
            );
          })}
        </nav>

        <div className="mt-5 flex items-end justify-between gap-4">
          <div>
            <h2 className="gradient-text text-2xl font-bold tracking-tight">{sec.title}</h2>
            <p className="muted mt-1 text-sm">{sec.blurb}</p>
          </div>
          <label className="muted flex shrink-0 items-center gap-2 text-sm">
            <input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} className="h-4 w-4 accent-leaf-600" />
            To do only
          </label>
        </div>

        <ul className="mt-5 space-y-3">
          {rows.map((row) => (
            <ReviewCard key={row.key} row={row} answer={answers[row.key]} onSave={save} />
          ))}
        </ul>

        {secDone === sec.rows.length && section < REVIEW_SECTIONS.length - 1 && (
          <button className="btn-primary mt-6 w-full" onClick={() => { setSection(section + 1); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
            Next: {REVIEW_SECTIONS[section + 1].title} <Icon.Arrow />
          </button>
        )}
        {done === REVIEW_TOTAL && (
          <div className="card mt-6 animate-pop p-6 text-center">
            <Icon.Sparkle className="mx-auto h-8 w-8 text-sun-400 drop-shadow-[0_0_12px_rgba(255,197,66,.7)]" />
            <p className="mt-2 text-lg font-bold">Sign-off complete. Ẹ ṣé gan!</p>
            <p className="muted mt-1 text-sm">You can still change any answer; it saves as you tap.</p>
          </div>
        )}
      </main>
      <Toast message={toast} tone={tone} />
    </>
  );
}

function ReviewCard({
  row,
  answer,
  onSave,
}: {
  row: ReviewRow;
  answer?: StoredReviewAnswer;
  onSave: (row: ReviewRow, verdict: StoredReviewAnswer["verdict"], note?: string) => Promise<void>;
}) {
  const isQuestion = row.kind === "question";
  const [editing, setEditing] = useState(isQuestion ? !answer : answer?.verdict === "change");
  const [note, setNote] = useState(answer?.note ?? "");
  const ref = useRef<HTMLTextAreaElement>(null);
  const state = answer?.verdict;

  useEffect(() => {
    if (editing && !isQuestion) ref.current?.focus();
  }, [editing, isQuestion]);

  const tone = useMemo(() => {
    if (state === "ok") return "!ring-leaf-400/50";
    if (state === "change") return "!ring-sun-400/60";
    if (state === "answer") return "!ring-leaf-400/50";
    return "";
  }, [state]);

  return (
    <li className={`card animate-rise p-4 sm:p-5 ${tone}`}>
      <div className="flex items-start gap-3">
        {row.danger && <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-clay-500 shadow-glow-coral" aria-label="Danger sign" />}
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{row.title}</p>
          <p className="mt-1 text-[15px] leading-relaxed">{row.detail}</p>
          {row.list && (
            <div className="mt-3 rounded-2xl bg-clay-500/[.07] p-3 ring-1 ring-clay-400/20">
              <p className="eyebrow text-clay-400">{row.list.title}</p>
              <ol className="mt-2 grid list-decimal gap-x-6 gap-y-1 pl-5 text-[15px] sm:grid-cols-2">
                {row.list.items.map((item) => <li key={item}>{item}</li>)}
              </ol>
            </div>
          )}
          {row.extra && (
            <p className="mt-2 rounded-xl bg-sand-100 px-3 py-2 text-sm dark:bg-white/[.06]">
              <span className="faint text-xs font-semibold uppercase tracking-wide">Health worker sees · </span>
              {row.extra}
            </p>
          )}
        </div>
      </div>

      {isQuestion ? (
        <div className="mt-3">
          <textarea
            ref={ref}
            className="input min-h-[88px] text-[15px]"
            placeholder="Your answer…"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            onBlur={() => note.trim() && note.trim() !== (answer?.note ?? "") && onSave(row, "answer", note)}
          />
          <div className="mt-2 flex items-center justify-between">
            <span className="faint text-xs">{answer ? "Saved" : "Saves when you tap outside the box"}</span>
            <button className="btn-ghost min-h-[40px] px-4 text-sm" disabled={!note.trim()} onClick={() => onSave(row, "answer", note)}>
              Save answer
            </button>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <button
              className={`btn focus-ring px-3 text-[15px] ${state === "ok" ? "bg-gradient-to-r from-leaf-400 to-cyan-400 text-night-950 shadow-glow" : "bg-leaf-400/10 text-leaf-100 ring-1 ring-leaf-400/25 hover:bg-leaf-400/15"}`}
              onClick={() => { setEditing(false); onSave(row, "ok"); }}
              aria-pressed={state === "ok"}
            >
              <Icon.Check /> <span className="whitespace-nowrap">Looks right</span>
            </button>
            <button
              className={`btn focus-ring px-3 text-[15px] ${state === "change" ? "bg-sun-400 text-night-950 shadow-[0_0_24px_-6px_rgba(255,197,66,.6)]" : "bg-sun-400/10 text-sun-100 ring-1 ring-sun-400/25 hover:bg-sun-400/15"}`}
              onClick={() => setEditing(true)}
              aria-pressed={state === "change"}
            >
              <Icon.Pencil /> <span className="whitespace-nowrap">Needs change</span>
            </button>
          </div>
          {editing && (
            <div className="mt-3 animate-rise">
              <textarea
                ref={ref}
                className="input min-h-[80px] text-[15px]"
                placeholder="What should change? (a word or two is fine)"
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
              <div className="mt-2 flex justify-end gap-2">
                <button className="btn-ghost min-h-[40px] px-4 text-sm" onClick={() => setEditing(false)}>Cancel</button>
                <button className="btn-primary min-h-[40px] px-4 text-sm" disabled={!note.trim()} onClick={() => { onSave(row, "change", note); }}>
                  Save change
                </button>
              </div>
            </div>
          )}
          {state === "change" && !editing && answer?.note && (
            <p className="mt-2 text-sm"><span className="faint">Your note: </span>{answer.note}</p>
          )}
        </>
      )}
    </li>
  );
}
