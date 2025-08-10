// server/cache.ts
type Entry<T> = { v: T; t: number }
const store = new Map<string, Entry<any>>()
const TTL = 5 * 60 * 1000 // 5 minutes

export function getCached<T>(k:string): T | null {
  const e = store.get(k)
  if (!e) return null
  if (Date.now() - e.t > TTL) { store.delete(k); return null }
  return e.v as T
}
export function setCached<T>(k:string, v:T){ store.set(k, { v, t: Date.now() }) }


