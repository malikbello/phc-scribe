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
                className={`chip focus-ring shrink-0 ${active ? "border-leaf-600 bg-leaf-600 text-white dark:border-leaf-500 dark:bg-leaf-500 dark:text-night-900" : "border-sand-300 bg-white dark:border-night-600 dark:bg-night-800"}`}
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
            <h2 className="text-2xl font-bold">{sec.title}</h2>
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
            <Icon.Sparkle className="mx-auto h-8 w-8 text-sun-400" />
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
    if (state === "ok") return "ring-2 ring-leaf-500/60";
    if (state === "change") return "ring-2 ring-sun-400/80";
    if (state === "answer") return "ring-2 ring-leaf-500/60";
    return "";
  }, [state]);

  return (
    <li className={`card animate-rise p-4 sm:p-5 ${tone}`}>
      <div className="flex items-start gap-3">
        {row.danger && <span className="mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full bg-clay-500" aria-label="Danger sign" />}
        <div className="min-w-0 flex-1">
          <p className="font-semibold">{row.title}</p>
          <p className="mt-1 text-[15px] leading-relaxed">{row.detail}</p>
          {row.extra && (
            <p className="mt-2 rounded-xl bg-sand-100 px-3 py-2 text-sm dark:bg-night-700">
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
              className={`btn focus-ring px-3 text-[15px] ${state === "ok" ? "bg-leaf-600 text-white dark:bg-leaf-500 dark:text-night-900" : "bg-leaf-50 text-leaf-700 hover:bg-leaf-100 dark:bg-night-700 dark:text-leaf-500"}`}
              onClick={() => { setEditing(false); onSave(row, "ok"); }}
              aria-pressed={state === "ok"}
            >
              <Icon.Check /> <span className="whitespace-nowrap">Looks right</span>
            </button>
            <button
              className={`btn focus-ring px-3 text-[15px] ${state === "change" ? "bg-sun-400 text-ink" : "bg-sun-100 text-sun-600 hover:brightness-95 dark:bg-night-700 dark:text-sun-400"}`}
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
