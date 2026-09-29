// Tap-to-select evidence: the transcript is split into word tokens with offsets. Tapping
// words selects a contiguous range; the evidence is the exact transcript substring for
// that range, so it is verbatim by construction.

export type Token = { text: string; start: number; end: number };

export function tokenize(text: string): Token[] {
  const out: Token[] = [];
  const re = /\S+/gu;
  let m: RegExpExecArray | null;
  while ((m = re.exec(text)) !== null) out.push({ text: m[0], start: m.index, end: m.index + m[0].length });
  return out;
}

export type Range = { from: number; to: number } | null;

/** Tapping logic: first tap selects one word; a second tap extends to a range; tapping an
 * end of an existing range shrinks back to that single word. */
export function tap(range: Range, i: number): Range {
  if (!range) return { from: i, to: i };
  if (range.from === range.to) {
    if (range.from === i) return null;
    return { from: Math.min(range.from, i), to: Math.max(range.from, i) };
  }
  if (i === range.from || i === range.to) return { from: i, to: i };
  return { from: Math.min(range.from, i), to: Math.max(range.to, i) };
}

const LEAD = /^[\s"'“‘(\[«]+/u;
const TRAIL = /[\s"'”’)\]».,;:!?]+$/u;

/** The exact substring covered by the range, with surrounding punctuation trimmed. */
export function evidenceFor(text: string, tokens: Token[], range: Range): string {
  if (!range) return "";
  const raw = text.slice(tokens[range.from].start, tokens[range.to].end);
  const trimmed = raw.replace(LEAD, "").replace(TRAIL, "");
  return trimmed || raw;
}
