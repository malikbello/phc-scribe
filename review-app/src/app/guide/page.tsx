"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Icon, Spinner, TopBar } from "@/components/ui";
import { api, post } from "@/lib/client";
import type { Role } from "@/lib/content";

type Me = { reviewer: { role: Role }; acks: Record<string, string> };

// The in-app guide: everything a reviewer needs before starting, written for the
// screens they will see. Sections depend on the role.
export default function GuidePage() {
  const [me, setMe] = useState<Me | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Me>("/api/me").then(setMe).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="p-6 text-clay-400">{error}</p>;
  if (!me) return (<><TopBar title="Guide" /><div className="py-24"><Spinner /></div></>);

  const role = me.reviewer.role;
  const clinical = role === "clinician" || role === "admin";
  const pharmacist = role === "pharmacist";
  const read = Boolean(me.acks.guide);

  async function confirm() {
    setSaving(true);
    try {
      await post("/api/ack", { step: "guide" });
      window.location.href = "/";
    } catch (e) {
      setError((e as Error).message);
      setSaving(false);
    }
  }

  return (
    <>
      <TopBar title="Guide" />
      <main className="mx-auto max-w-2xl px-4 pb-24 pt-4 text-[16px] leading-relaxed">
        <p className="eyebrow text-leaf-400">About 5 minutes</p>
        <h1 className="gradient-text mt-1 text-3xl font-bold tracking-tight">How to help</h1>
        <p className="muted mt-2">
          PHC Scribe listens to what a pregnant woman says at an antenatal visit, writes it down as a record, and warns the
          health worker about danger signs. Your answers check that it is clinically right, and build the test set that
          proves whether it works.
        </p>

        <Section n={1} title="What you will do">
          <ol className="list-decimal space-y-1 pl-5">
            <li>Read this guide (you are here).</li>
            {clinical && <li><b>Clinical sign-off</b>: check our danger-sign rules, findings, wordings and medicines. About 1.5 hours.</li>}
            {pharmacist && <li><b>Medicines check</b>: check the medicines the app records and tell us the names people use. About 20 minutes.</li>}
            <li><b>Practice set</b>: label 20 short antenatal cases on your own. About 30 minutes. We compare everyone&apos;s answers to see if the rules are clear.</li>
            <li><b>Benchmark labelling</b> (later): more cases of the same kind. It appears on your home screen when it&apos;s ready.</li>
          </ol>
          <p className="muted mt-2">Your home screen shows these steps in order, with a tick when each is done. Everything saves as you go, so you can stop and continue any time, on any device.</p>
        </Section>

        {(clinical || pharmacist) && (
          <Section n={2} title={clinical ? "Clinical sign-off" : "Medicines check"}>
            <p>Each card shows one thing the app does. Tap:</p>
            <ul className="mt-2 space-y-1">
              <li><b className="text-leaf-400">Looks right</b> if you agree.</li>
              <li><b className="text-sun-400">Needs change</b> if not, then write what should change. A few words are enough.</li>
            </ul>
            <p className="mt-2">Question cards have a box instead: type your answer and tap <b>Save answer</b>. A short answer is perfect.</p>
            {clinical && (
              <p className="mt-2">There are six steps: <b>Danger-sign rules</b>, <b>Findings list</b>, <b>Open questions</b>, <b>How notes are worded</b>, <b>Medicines</b> and <b>Before the freeze</b>. Answer from your own practice; there are no trick questions.</p>
            )}
            {pharmacist && (
              <p className="mt-2">You will see one card per medicine (iron and folic acid, IPTp-SP, Td vaccine, deworming, calcium), then two questions: the names people use for them, and anything missing from the list. Brand names, Pidgin and Yoruba names are exactly what we need.</p>
            )}
          </Section>
        )}

        <Section n={clinical || pharmacist ? 3 : 2} title="Labelling a case">
          <p>You will see what a woman said, or a short clinic note. For each finding <b>about the pregnant woman herself</b>:</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5">
            <li><b>Tap the words</b> that show it. Tap a second word to include everything in between. Tap an end again to start over.</li>
            <li><b>Choose the finding</b> from the list under <i>Is it…</i> (you can search).</li>
            <li>Choose how it was said: <b>Present</b>, <b>Absent</b> (&quot;no bleeding&quot;), <b>Possible</b> (unsure or &quot;maybe&quot;), or <b>Past pregnancy</b>.</li>
          </ol>
          <p className="mt-2">Add as many findings as the text has, then tap <b>Save &amp; next</b> at the bottom.</p>
          <ul className="mt-2 space-y-1">
            <li>Nothing to record? Tap <b>Nothing to record</b>. That is a valid answer.</li>
            <li>Not about pregnancy, or can&apos;t be understood? Tap <b>Skip</b> and pick a reason.</li>
            <li>Made a mistake? The <b>clock icon</b> at the top takes you back to your previous case.</li>
            <li>Forgot a rule? The <b>book icon</b> at the top shows the five rules below.</li>
          </ul>
          <p className="muted mt-2">About 1 minute per case is normal. Don&apos;t agonise: if unsure, choose your best answer and write a note.</p>
        </Section>

        <Section n={clinical || pharmacist ? 4 : 3} title="The five rules that matter">
          <ol className="list-decimal space-y-2 pl-5">
            <li><b>Record what is said, not what you would diagnose.</b> &quot;Headache and BP 150/100&quot; is <i>Headache</i>, not pre-eclampsia. The app&apos;s rules do the diagnosing.</li>
            <li><b>Only the woman herself.</b> Not her baby after birth, her husband or her mother.</li>
            <li><b>Include the cue in the words you tap.</b> For absent, possible or past findings, tap &quot;no bleeding&quot;, not just &quot;bleeding&quot;.</li>
            <li><b>Severe only if the words say so</b> (severe, very bad, won&apos;t stop, &quot;gidigidi&quot;). Otherwise choose the ordinary finding.</li>
            <li><b>When torn, choose what a cautious clinician would act on.</b> Use <i>Possible</i> rather than leaving a danger sign out.</li>
          </ol>
          <p className="mt-2">Past pregnancy and now in one sentence? Add two findings: &quot;bled in her last pregnancy, no bleeding now&quot; is <i>Past pregnancy</i> and <i>Absent</i>.</p>
        </Section>

        <Section n={clinical || pharmacist ? 5 : 4} title="Please keep it confidential">
          <p>The cases are real people&apos;s words, shared for research. Don&apos;t screenshot, copy or share them, and don&apos;t discuss your answers with each other until everyone has finished the practice set: we need your independent judgement.</p>
          <p className="mt-2">Questions? Message Malik.</p>
        </Section>

        <div className="mt-8">
          {read ? (
            <Link href="/" className="btn-primary w-full"><Icon.Check /> You&apos;ve read this. Back home</Link>
          ) : (
            <button className="btn-primary w-full" onClick={confirm} disabled={saving}>
              <Icon.Check /> I&apos;ve read this. Start
            </button>
          )}
        </div>
      </main>
    </>
  );
}

function Section({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <section className="card mt-5 p-5 sm:p-6">
      <div className="flex items-center gap-3">
        <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-gradient-to-br from-leaf-400 to-cyan-400 text-sm font-bold text-night-950">{n}</span>
        <h2 className="text-xl font-bold tracking-tight">{title}</h2>
      </div>
      <div className="mt-3">{children}</div>
    </section>
  );
}
