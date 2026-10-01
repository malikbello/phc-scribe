import { agreement } from "./agreement";
import { candidates, pickDouble, teamComplete } from "./assign";
import { reviewKeysFor, type Role } from "./content";
import { HttpError } from "./server";
import {
  evidenceInTranscript,
  evidenceLongEnough,
  type Label,
  type LabelInput,
  type QueueItem,
  type QueueMeta,
  type QueueUpload,
  type ReviewAnswer,
  type StoredReviewAnswer,
  type AckStep,
  type AdjudicationInput,
  isSpeechSource,
  SPEECH_SKIP_REASONS,
} from "./schema";
import { store } from "./store";
import { basisOf, causesOf, resolve, type Adjudication, type Cause, type Resolution } from "./adjudicate";

// Key layout (all under one Redis database):
//   queues                      set of queue ids
//   q:{id}:meta                 QueueMeta (order + double-label subset)
//   q:{id}:items                hash itemId -> QueueItem
//   q:{id}:labels:{itemId}      hash reviewerId -> Label
//   q:{id}:counts               hash itemId -> number of distinct labellers
//   q:{id}:done:{rid}           set of itemIds the reviewer has labelled
//   q:{id}:time:{rid}           hash {n, ms} for time estimates
//   lock:{id}:{itemId}          reviewerId, 15-minute expiry
//   rev:{rid}                   hash reviewKey -> StoredReviewAnswer
//   ack:{rid}                   hash step -> ISO time (onboarding steps, e.g. "guide")
//   q:{id}:adj                  hash itemId -> Adjudication (clinician's gold decision)

const LOCK_SECONDS = 15 * 60;

const k = {
  meta: (q: string) => `q:${q}:meta`,
  items: (q: string) => `q:${q}:items`,
  labels: (q: string, i: string) => `q:${q}:labels:${i}`,
  counts: (q: string) => `q:${q}:counts`,
  done: (q: string, r: string) => `q:${q}:done:${r}`,
  time: (q: string, r: string) => `q:${q}:time:${r}`,
  lock: (q: string, i: string) => `lock:${q}:${i}`,
  review: (r: string) => `rev:${r}`,
  ack: (r: string) => `ack:${r}`,
  adj: (q: string) => `q:${q}:adj`,
};

function slug(title: string): string {
  const base = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 32) || "queue";
  return `${base}-${Date.now().toString(36)}`;
}

export async function createQueue(up: QueueUpload, createdBy: string): Promise<QueueMeta> {
  const s = store();
  const ids = up.items.map((i) => i.item_id);
  if (new Set(ids).size !== ids.length) throw new HttpError(400, "Duplicate item_id in upload");
  const meta: QueueMeta = {
    id: slug(up.title),
    title: up.title,
    description: up.description,
    createdAt: new Date().toISOString(),
    createdBy,
    showHints: up.showHints,
    order: ids,
    double: up.everyone ? [] : pickDouble(ids, up.doubleShare),
    ...(up.everyone ? { everyone: true } : {}),
  };
  for (let i = 0; i < up.items.length; i += 100) {
    const chunk = up.items.slice(i, i + 100);
    await s.hset(k.items(meta.id), Object.fromEntries(chunk.map((it) => [it.item_id, it])));
  }
  await s.set(k.meta(meta.id), meta);
  await s.sadd("queues", meta.id);
  return meta;
}

/** Switch calibration mode on or off. Labels already given are kept. */
export async function setEveryone(queueId: string, everyone: boolean): Promise<QueueMeta> {
  const meta = await getMeta(queueId);
  const next: QueueMeta = { ...meta, everyone };
  await store().set(k.meta(queueId), next);
  return next;
}

/** Delete a set that nobody has labelled yet (e.g. to re-upload with other settings). */
export async function deleteQueue(queueId: string): Promise<void> {
  const s = store();
  await getMeta(queueId);
  const counts = await s.hgetall<number>(k.counts(queueId));
  if (Object.values(counts).some((n) => Number(n) > 0)) {
    throw new HttpError(409, "This set already has labels. Export them; sets with labels can't be deleted.");
  }
  await s.srem("queues", queueId);
  await s.del(k.items(queueId));
  await s.del(k.counts(queueId));
  await s.del(k.meta(queueId));
}

export async function getMeta(queueId: string): Promise<QueueMeta> {
  const meta = await store().get<QueueMeta>(k.meta(queueId));
  if (!meta) throw new HttpError(404, "Queue not found");
  return meta;
}

async function getItem(queueId: string, itemId: string): Promise<QueueItem> {
  const item = await store().hget<QueueItem>(k.items(queueId), itemId);
  if (!item) throw new HttpError(404, "Item not found");
  return item;
}

export type ClientItem = {
  itemId: string;
  language: string;
  /** Where the item came from; "wazobia" items are real everyday speech (guidelines §10). */
  source: string;
  transcript: string;
  hints: QueueItem["hints"];
  double: boolean;
  mine: Label | null;
};

function toClient(meta: QueueMeta, item: QueueItem, mine: Label | null): ClientItem {
  return {
    itemId: item.item_id,
    language: item.language,
    source: item.source,
    transcript: item.transcript,
    hints: meta.showHints ? item.hints : [],
    double: Boolean(meta.everyone) || meta.double.includes(item.item_id),
    mine,
  };
}

export type QueueProgress = {
  id: string;
  title: string;
  description?: string;
  total: number;
  mineDone: number;
  mineAvailable: number;
  teamComplete: number;
  avgMs: number | null;
  everyone: boolean;
};

export async function listQueues(rid: string): Promise<QueueProgress[]> {
  const s = store();
  const ids = await s.smembers("queues");
  const out: QueueProgress[] = [];
  for (const id of ids) {
    const meta = await s.get<QueueMeta>(k.meta(id));
    if (!meta) continue;
    const double = new Set(meta.double);
    const counts = await s.hgetall<number>(k.counts(id));
    const mine = new Set(await s.smembers(k.done(id, rid)));
    const time = await s.hgetall<number>(k.time(id, rid));
    const everyone = Boolean(meta.everyone);
    out.push({
      id,
      title: meta.title,
      description: meta.description,
      total: meta.order.length,
      mineDone: mine.size,
      mineAvailable: candidates(meta.order, double, counts, mine, everyone).length,
      teamComplete: teamComplete(meta.order, double, counts, everyone),
      avgMs: time.n ? Number(time.ms) / Number(time.n) : null,
      everyone,
    });
  }
  return out.sort((a, b) => a.title.localeCompare(b.title));
}

export async function nextItem(queueId: string, rid: string): Promise<ClientItem | null> {
  const s = store();
  const meta = await getMeta(queueId);
  const double = new Set(meta.double);
  const counts = await s.hgetall<number>(k.counts(queueId));
  const mine = new Set(await s.smembers(k.done(queueId, rid)));
  const everyone = Boolean(meta.everyone);
  for (const id of candidates(meta.order, double, counts, mine, everyone).slice(0, 60)) {
    const lockKey = k.lock(queueId, id);
    // Double and calibration items may be worked on by several people at once; single items are locked.
    if (!everyone && !double.has(id)) {
      const got = await s.set(lockKey, rid, { nx: true, ex: LOCK_SECONDS });
      if (!got && (await s.get<string>(lockKey)) !== rid) continue;
    }
    return toClient(meta, await getItem(queueId, id), null);
  }
  return null;
}

export async function itemForReviewer(queueId: string, itemId: string, rid: string): Promise<ClientItem> {
  const meta = await getMeta(queueId);
  const item = await getItem(queueId, itemId);
  const mine = await store().hget<Label>(k.labels(queueId, itemId), rid);
  return toClient(meta, item, mine);
}

export async function myHistory(queueId: string, rid: string): Promise<string[]> {
  const meta = await getMeta(queueId);
  const mine = new Set(await store().smembers(k.done(queueId, rid)));
  return meta.order.filter((id) => mine.has(id));
}

export async function saveLabel(queueId: string, rid: string, input: LabelInput): Promise<Label> {
  const s = store();
  const item = await getItem(queueId, input.itemId);
  if (input.status === "skip" && input.skipReason && isSpeechSource(item.source) && !SPEECH_SKIP_REASONS.has(input.skipReason)) {
    throw new HttpError(400, "In real speech sets, general talk is labelled Nothing to record, not skipped");
  }
  for (const f of input.findings) {
    if (!evidenceLongEnough(f.evidence.text)) {
      throw new HttpError(400, `Evidence for ${f.concept} is too short: select a few more words`);
    }
    if (!evidenceInTranscript(item.transcript, f.evidence.text)) {
      throw new HttpError(400, `Evidence for ${f.concept} is not exact text from the item`);
    }
  }
  const label: Label = {
    item_id: input.itemId,
    status: input.status,
    ...(input.status === "skip" && input.skipReason ? { skip_reason: input.skipReason } : {}),
    findings: input.status === "skip" ? [] : input.findings,
    labeller: rid,
    labelled_at: new Date().toISOString(),
    ...(input.note?.trim() ? { note: input.note.trim() } : {}),
    ...(input.elapsedMs !== undefined ? { elapsed_ms: input.elapsedMs } : {}),
  };
  const labelsKey = k.labels(queueId, input.itemId);
  const existed = await s.hget<Label>(labelsKey, rid);
  await s.hset(labelsKey, { [rid]: label });
  if (!existed) {
    await s.hincrby(k.counts(queueId), input.itemId, 1);
    await s.sadd(k.done(queueId, rid), input.itemId);
    if (input.elapsedMs !== undefined && input.elapsedMs < 20 * 60_000) {
      await s.hincrby(k.time(queueId, rid), "n", 1);
      await s.hincrby(k.time(queueId, rid), "ms", input.elapsedMs);
    }
  }
  await s.del(k.lock(queueId, input.itemId));
  return label;
}

export async function saveReview(rid: string, a: ReviewAnswer): Promise<StoredReviewAnswer> {
  const stored: StoredReviewAnswer = { ...a, note: a.note?.trim() || undefined, at: new Date().toISOString() };
  await store().hset(k.review(rid), { [a.key]: stored });
  return stored;
}

export async function myReview(rid: string): Promise<Record<string, StoredReviewAnswer>> {
  return store().hgetall<StoredReviewAnswer>(k.review(rid));
}

/** Sign-off progress over the steps this reviewer's role works through. */
export async function reviewProgress(rid: string, role: Role): Promise<{ done: number; total: number }> {
  const keys = reviewKeysFor(role);
  const done = Object.keys(await myReview(rid)).filter((k) => keys.has(k)).length;
  return { done, total: keys.size };
}

/** Onboarding steps the reviewer has confirmed (e.g. read the guide). */
export async function myAcks(rid: string): Promise<Record<string, string>> {
  return store().hgetall<string>(k.ack(rid));
}

export async function saveAck(rid: string, step: AckStep): Promise<void> {
  await store().hset(k.ack(rid), { [step]: new Date().toISOString() });
}

// ---------------------------------------------------------------- admin

export async function allLabels(queueId: string): Promise<Record<string, Record<string, Label>>> {
  const s = store();
  const meta = await getMeta(queueId);
  const counts = await s.hgetall<number>(k.counts(queueId));
  const ids = meta.order.filter((id) => Number(counts[id] ?? 0) > 0);
  const hashes = await s.hgetallMany<Label>(ids.map((id) => k.labels(queueId, id)));
  return Object.fromEntries(ids.map((id, i) => [id, hashes[i]]));
}

export async function queueStats(queueId: string, reviewerIds: string[]) {
  const s = store();
  const meta = await getMeta(queueId);
  const labels = await allLabels(queueId);
  const perReviewer: Record<string, number> = {};
  for (const rid of reviewerIds) perReviewer[rid] = (await s.smembers(k.done(queueId, rid))).length;
  const double = new Set(meta.double);
  const everyone = Boolean(meta.everyone);
  // Calibration sets compare everyone on every item; other sets use the double-label subset.
  const doubleLabels = everyone ? labels : Object.fromEntries(Object.entries(labels).filter(([id]) => double.has(id)));
  const counts = await s.hgetall<number>(k.counts(queueId));
  return {
    id: meta.id,
    title: meta.title,
    everyone,
    total: meta.order.length,
    doubleTotal: everyone ? meta.order.length : meta.double.length,
    labelledItems: Object.keys(labels).length,
    complete: teamComplete(meta.order, double, counts, everyone),
    perReviewer,
    agreement: agreement(doubleLabels),
  };
}

export async function itemsById(queueId: string, ids: string[]): Promise<Record<string, QueueItem>> {
  const out: Record<string, QueueItem> = {};
  for (const id of ids) out[id] = await getItem(queueId, id);
  return out;
}

export async function allReviews(reviewerIds: string[]) {
  const out: Record<string, Record<string, StoredReviewAnswer>> = {};
  for (const rid of reviewerIds) out[rid] = await myReview(rid);
  return out;
}

// ---- Gold labels and adjudication (lib/adjudicate.ts has the rules) ----

/** Items whose labels decide gold together: every item of a practice set, the double subset otherwise. */
function multiLabelled(meta: QueueMeta, labels: Record<string, Record<string, Label>>): string[] {
  return meta.order.filter((id) => Object.keys(labels[id] ?? {}).length >= 2);
}

export type PendingItem = {
  itemId: string;
  language: string;
  source: string;
  transcript: string;
  why: string;
  /** Distinct answers, anonymised (A, B, ...) and grouped; who gave them is never shown. */
  answers: { name: string; count: number; status: Label["status"]; skip_reason?: Label["skip_reason"]; findings: Label["findings"] }[];
};

export async function adjudicationState(queueId: string) {
  const meta = await getMeta(queueId);
  const labels = await allLabels(queueId);
  const adj = await store().hgetall<Adjudication>(k.adj(queueId));
  const counts: Record<Resolution | "pending" | "unlabelled", number> = { single: 0, agreed: 0, majority: 0, adjudicated: 0, pending: 0, unlabelled: 0 };
  const causes: Partial<Record<Cause, number>> = {};
  const pending: string[] = [];
  const gold: Label[] = [];
  for (const id of meta.order) {
    const ls = Object.values(labels[id] ?? {});
    const r = resolve(ls, adj[id]);
    if (r.state === "resolved") {
      counts[r.resolution]++;
      gold.push(r.gold);
    } else counts[r.state]++;
    if (r.state === "pending") pending.push(id);
    if (ls.length >= 2) for (const c of causesOf(ls)) causes[c] = (causes[c] ?? 0) + 1;
  }
  return { meta, labels, adj, counts, causes, pending, gold, multi: multiLabelled(meta, labels).length };
}

export async function pendingCounts(): Promise<{ id: string; title: string; pending: number }[]> {
  const ids = await store().smembers("queues");
  const out = [];
  for (const id of ids) {
    const st = await adjudicationState(id).catch(() => null);
    if (st && st.pending.length) out.push({ id, title: st.meta.title, pending: st.pending.length });
  }
  return out.sort((a, b) => a.title.localeCompare(b.title));
}

export async function nextPending(queueId: string, after?: string): Promise<PendingItem | null> {
  const st = await adjudicationState(queueId);
  const start = after ? st.pending.indexOf(after) + 1 : 0;
  const id = st.pending[start] ?? st.pending[0];
  if (!id) return null;
  const item = await getItem(queueId, id);
  const ls = Object.values(st.labels[id] ?? {}).sort((a, b) => a.labeller.localeCompare(b.labeller));
  const r = resolve(ls, st.adj[id]);
  const groups = new Map<string, Label[]>();
  for (const l of ls) {
    const key = l.status === "skip" ? "skip" : l.findings.map((f) => `${f.concept}|${f.assertion}`).sort().join(",") || "nothing";
    groups.set(key, [...(groups.get(key) ?? []), l]);
  }
  return {
    itemId: id,
    language: item.language,
    source: item.source,
    transcript: item.transcript,
    why: r.state === "pending" ? r.why : "",
    answers: [...groups.values()].map((g, i) => ({
      name: String.fromCharCode(65 + i),
      count: g.length,
      status: g[0].status,
      ...(g[0].skip_reason ? { skip_reason: g[0].skip_reason } : {}),
      findings: g[0].status === "skip" ? [] : g[0].findings,
    })),
  };
}

export async function saveAdjudication(queueId: string, rid: string, input: AdjudicationInput): Promise<Adjudication> {
  const item = await getItem(queueId, input.itemId);
  for (const f of input.findings) {
    if (!evidenceInTranscript(item.transcript, f.evidence.text)) {
      throw new HttpError(400, `Evidence for ${f.concept} is not exact text from the item`);
    }
  }
  const labels = Object.values((await allLabels(queueId))[input.itemId] ?? {});
  if (labels.length < 2) throw new HttpError(409, "Only items with two or more labels are adjudicated");
  const decision: Adjudication = {
    item_id: input.itemId,
    status: input.status,
    ...(input.status === "skip" && input.skipReason ? { skip_reason: input.skipReason } : {}),
    findings: input.status === "skip" ? [] : input.findings,
    reason: input.reason,
    adjudicator: rid,
    adjudicated_at: new Date().toISOString(),
    basis: basisOf([...labels].sort((a, b) => a.labeller.localeCompare(b.labeller))),
  };
  await store().hset(k.adj(queueId), { [input.itemId]: decision });
  return decision;
}
