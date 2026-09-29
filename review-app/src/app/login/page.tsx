"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/Logo";
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
      <div className="w-full max-w-sm">
        <div className="mb-10 flex animate-rise items-center gap-3">
          <Logo size={52} spin />
          <div>
            <p className="text-lg font-bold leading-tight tracking-tight">PHC Scribe</p>
            <p className="eyebrow text-leaf-400">Clinical review</p>
          </div>
        </div>
        <h1 className="gradient-text animate-rise text-[34px] font-bold leading-[1.1] tracking-tight [animation-delay:60ms]">
          Ẹ káàbọ̀.
          <br />
          Welcome.
        </h1>
        <p className="muted mt-3 animate-rise [animation-delay:120ms]">
          Enter the access code Malik sent you. It keeps this workspace private to our team.
        </p>
        <form onSubmit={submit} className="card mt-7 animate-rise space-y-3 p-4 [animation-delay:180ms]">
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
          {error && <p className="text-sm font-medium text-clay-400" role="alert">{error}</p>}
          <button className="btn-primary w-full text-base" disabled={busy || !code.trim()}>
            {busy ? "Signing in…" : "Continue"} <Icon.Arrow />
          </button>
        </form>
        <p className="faint mt-8 flex items-center gap-2 text-xs"><Icon.Lock className="h-4 w-4" /> Private team workspace · items are confidential</p>
      </div>
    </main>
  );
}
