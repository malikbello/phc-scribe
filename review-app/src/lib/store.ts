import { Redis } from "@upstash/redis";

// The small key-value surface the app needs. Production uses Upstash Redis (connected
// through Vercel Storage, which injects KV_REST_API_URL / KV_REST_API_TOKEN). Local
// development and tests use an in-memory store; production refuses to run without Redis.

export interface Store {
  get<T>(key: string): Promise<T | null>;
  set(key: string, value: unknown, opts?: { nx?: boolean; ex?: number }): Promise<boolean>;
  del(key: string): Promise<void>;
  hget<T>(key: string, field: string): Promise<T | null>;
  hset(key: string, values: Record<string, unknown>): Promise<void>;
  hgetall<T>(key: string): Promise<Record<string, T>>;
  /** Several hashes in one round trip (pipelined on Redis). */
  hgetallMany<T>(keys: string[]): Promise<Record<string, T>[]>;
  hdel(key: string, field: string): Promise<void>;
  hincrby(key: string, field: string, by: number): Promise<number>;
  sadd(key: string, member: string): Promise<void>;
  smembers(key: string): Promise<string[]>;
  incrWithTtl(key: string, ttlSeconds: number): Promise<number>;
  ping(): Promise<boolean>;
}

class UpstashStore implements Store {
  constructor(private r: Redis) {}
  async get<T>(key: string) {
    return (await this.r.get<T>(key)) ?? null;
  }
  async set(key: string, value: unknown, opts: { nx?: boolean; ex?: number } = {}) {
    const res = opts.nx
      ? await this.r.set(key, value, opts.ex ? { nx: true, ex: opts.ex } : { nx: true })
      : await this.r.set(key, value, opts.ex ? { ex: opts.ex } : undefined);
    return res === "OK";
  }
  async del(key: string) {
    await this.r.del(key);
  }
  async hget<T>(key: string, field: string) {
    return (await this.r.hget<T>(key, field)) ?? null;
  }
  async hset(key: string, values: Record<string, unknown>) {
    if (Object.keys(values).length) await this.r.hset(key, values);
  }
  async hgetall<T>(key: string) {
    return ((await this.r.hgetall<Record<string, T>>(key)) ?? {}) as Record<string, T>;
  }
  async hgetallMany<T>(keys: string[]) {
    const out: Record<string, T>[] = [];
    for (let i = 0; i < keys.length; i += 200) {
      const p = this.r.pipeline();
      for (const k of keys.slice(i, i + 200)) p.hgetall(k);
      const res = (await p.exec()) as (Record<string, T> | null)[];
      out.push(...res.map((r) => r ?? {}));
    }
    return out;
  }
  async hdel(key: string, field: string) {
    await this.r.hdel(key, field);
  }
  async hincrby(key: string, field: string, by: number) {
    return this.r.hincrby(key, field, by);
  }
  async sadd(key: string, member: string) {
    await this.r.sadd(key, member);
  }
  async smembers(key: string) {
    return (await this.r.smembers(key)).map(String);
  }
  async incrWithTtl(key: string, ttlSeconds: number) {
    const n = await this.r.incr(key);
    if (n === 1) await this.r.expire(key, ttlSeconds);
    return n;
  }
  async ping() {
    return (await this.r.ping()) === "PONG";
  }
}

type Entry = { v: unknown; exp?: number };

export class MemoryStore implements Store {
  private m = new Map<string, Entry>();
  private live(key: string): Entry | undefined {
    const e = this.m.get(key);
    if (e && e.exp !== undefined && e.exp < Date.now()) {
      this.m.delete(key);
      return undefined;
    }
    return e;
  }
  private clone<T>(v: T): T {
    return v === undefined ? v : (JSON.parse(JSON.stringify(v)) as T);
  }
  async get<T>(key: string) {
    const e = this.live(key);
    return e ? this.clone(e.v as T) : null;
  }
  async set(key: string, value: unknown, opts: { nx?: boolean; ex?: number } = {}) {
    if (opts.nx && this.live(key)) return false;
    this.m.set(key, { v: this.clone(value), exp: opts.ex ? Date.now() + opts.ex * 1000 : undefined });
    return true;
  }
  async del(key: string) {
    this.m.delete(key);
  }
  private hash(key: string): Record<string, unknown> {
    const e = this.live(key);
    if (!e) {
      const h: Record<string, unknown> = {};
      this.m.set(key, { v: h });
      return h;
    }
    return e.v as Record<string, unknown>;
  }
  async hget<T>(key: string, field: string) {
    const v = this.hash(key)[field];
    return v === undefined ? null : this.clone(v as T);
  }
  async hset(key: string, values: Record<string, unknown>) {
    Object.assign(this.hash(key), this.clone(values));
  }
  async hgetall<T>(key: string) {
    return this.clone(this.hash(key)) as Record<string, T>;
  }
  async hgetallMany<T>(keys: string[]) {
    return Promise.all(keys.map((k) => this.hgetall<T>(k)));
  }
  async hdel(key: string, field: string) {
    delete this.hash(key)[field];
  }
  async hincrby(key: string, field: string, by: number) {
    const h = this.hash(key);
    h[field] = Number(h[field] ?? 0) + by;
    return h[field] as number;
  }
  async sadd(key: string, member: string) {
    const e = this.live(key);
    const s = new Set<string>((e?.v as string[]) ?? []);
    s.add(member);
    this.m.set(key, { v: [...s] });
  }
  async smembers(key: string) {
    return [...((this.live(key)?.v as string[]) ?? [])];
  }
  async incrWithTtl(key: string, ttlSeconds: number) {
    const e = this.live(key);
    const n = Number(e?.v ?? 0) + 1;
    this.m.set(key, { v: n, exp: e?.exp ?? Date.now() + ttlSeconds * 1000 });
    return n;
  }
  async ping() {
    return true;
  }
}

const g = globalThis as unknown as { __phcStore?: Store };

export function store(): Store {
  if (g.__phcStore) return g.__phcStore;
  const url = process.env.KV_REST_API_URL ?? process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.KV_REST_API_TOKEN ?? process.env.UPSTASH_REDIS_REST_TOKEN;
  if (url && token) {
    g.__phcStore = new UpstashStore(new Redis({ url, token }));
  } else if (process.env.NODE_ENV === "production") {
    throw new Error("Redis is not configured: connect Upstash Redis in Vercel Storage");
  } else {
    g.__phcStore = new MemoryStore();
  }
  return g.__phcStore;
}
