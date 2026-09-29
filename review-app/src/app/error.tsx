"use client";

export default function Error({ reset }: { error: Error; reset: () => void }) {
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="card max-w-sm animate-pop p-8 text-center">
        <p className="eyebrow text-clay-400">Something went wrong</p>
        <h1 className="gradient-text mt-2 text-2xl font-bold tracking-tight">We couldn't load this</h1>
        <p className="muted mt-2 text-sm">Your saved work is safe. Check your connection and try again.</p>
        <button className="btn-primary mt-6" onClick={reset}>Try again</button>
      </div>
    </main>
  );
}
