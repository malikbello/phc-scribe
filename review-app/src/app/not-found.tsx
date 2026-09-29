import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="card max-w-sm animate-pop p-8 text-center">
        <p className="eyebrow text-leaf-400">404</p>
        <h1 className="gradient-text mt-2 text-2xl font-bold tracking-tight">Nothing here</h1>
        <p className="muted mt-2 text-sm">That page doesn't exist, or the set was removed.</p>
        <Link href="/" className="btn-primary mt-6">Back home</Link>
      </div>
    </main>
  );
}
