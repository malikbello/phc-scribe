"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Icon } from "@/components/ui";
import { post } from "@/lib/client";

export default function LoginPage() {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await post("/api/login", { code });
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-sm animate-rise">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-leaf-600 text-white shadow-card">
            <svg viewBox="0 0 64 64" className="h-8 w-8" aria-hidden><path d="M14 36c7 0 9-12 14-12s8 18 16 18" fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round" /><circle cx="48" cy="20" r="6" fill="#f2b53a" /></svg>
          </div>
          <div>
            <p className="text-lg font-bold leading-tight">PHC Scribe</p>
            <p className="muted text-sm">Clinical review</p>
          </div>
        </div>
        <h1 className="text-[28px] font-bold leading-tight">Ẹ káàbọ̀. Welcome.</h1>
        <p className="muted mt-2">Enter the access code Malik sent you. It keeps the review private to our team.</p>
        <form onSubmit={submit} className="mt-6 space-y-3">
          <label htmlFor="code" className="sr-only">Access code</label>
          <input
            id="code"
            className="input text-lg tracking-wide"
            placeholder="Your access code"
            autoComplete="one-time-code"
            autoCapitalize="none"
            spellCheck={false}
            value={code}
            onChange={(e) => setCode(e.target.value)}
            required
          />
          {error && <p className="text-sm font-medium text-clay-600" role="alert">{error}</p>}
          <button className="btn-primary w-full text-base" disabled={busy || !code.trim()}>
            {busy ? "Signing in…" : "Continue"} <Icon.Arrow />
          </button>
        </form>
        <p className="faint mt-8 flex items-center gap-2 text-xs"><Icon.Lock className="h-4 w-4" /> Private team workspace. Items are confidential.</p>
      </div>
    </main>
  );
}
