// Light game layer for labelling: levels from items labelled (stored server-side, so they
// follow the reviewer across devices). Rewards steady progress only, never speed: fast
// labelling is not something we want to encourage.

export const PER_LEVEL = 25;
const RANKS = ["Listener", "Note-taker", "Scribe", "Senior scribe", "Lead scribe", "Master scribe"];

export type Level = { level: number; rank: string; intoLevel: number; toNext: number };

export function levelFor(done: number): Level {
  const n = Math.max(0, Math.floor(done));
  const level = Math.floor(n / PER_LEVEL) + 1;
  const intoLevel = n % PER_LEVEL;
  return { level, rank: RANKS[Math.min(level - 1, RANKS.length - 1)], intoLevel, toNext: PER_LEVEL - intoLevel };
}

/** The level reached by this save, if it crossed a level boundary. */
export function levelUp(before: number, after: number): Level | null {
  return levelFor(after).level > levelFor(before).level ? levelFor(after) : null;
}
