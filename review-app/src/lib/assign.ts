// Work assignment. Items in the double-label subset need two different labellers (for
// agreement statistics); every other item needs one. Double items are served first so
// the agreement sample fills early. A short lock stops two people getting the same
// single-label item at the same time.

export function required(itemId: string, double: ReadonlySet<string>): number {
  return double.has(itemId) ? 2 : 1;
}

export function candidates(
  order: readonly string[],
  double: ReadonlySet<string>,
  counts: Readonly<Record<string, number>>,
  mine: ReadonlySet<string>,
): string[] {
  const open = order.filter((id) => !mine.has(id) && (counts[id] ?? 0) < required(id, double));
  return [...open.filter((id) => double.has(id)), ...open.filter((id) => !double.has(id))];
}

/** Stable pseudo-random pick of the double-label subset (FNV-1a hash of the item id). */
export function pickDouble(ids: readonly string[], share: number): string[] {
  const n = Math.round(ids.length * Math.min(1, Math.max(0, share)));
  const h = (s: string) => {
    let x = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) {
      x ^= s.charCodeAt(i);
      x = Math.imul(x, 0x01000193) >>> 0;
    }
    return x;
  };
  return [...ids].sort((a, b) => h(a) - h(b) || a.localeCompare(b)).slice(0, n);
}

export function remainingMinutes(left: number, avgMs: number | null): number {
  const per = avgMs && avgMs > 5_000 ? avgMs : 60_000;
  return Math.max(0, Math.round((left * per) / 60_000));
}
