import fs from 'node:fs'
import path from 'node:path'

export type BulkJob = {
  id: string
  merchantId: string
  total: number
  processed: number
  status: 'queued'|'running'|'done'|'error'
  proposals: Array<{ sku:string; target:number; ourPrice?:number }>
  summary?: any
  error?: string
}

const FILE = path.join(process.cwd(), 'apps', 'kaspi_offers_dashboard', 'server', 'db', 'pricebot.jobs.json')

function ensureDir(){ const dir = path.dirname(FILE); if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true }) }
function readAll(): Record<string, BulkJob> { try { return JSON.parse(fs.readFileSync(FILE,'utf-8')) } catch { return {} } }
function writeAll(all: Record<string, BulkJob>){ ensureDir(); const tmp=FILE+'.tmp'; fs.writeFileSync(tmp, JSON.stringify(all,null,2)); fs.renameSync(tmp, FILE) }

export function createJob(merchantId: string, total: number): BulkJob {
  const all = readAll()
  const id = `${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`
  const job: BulkJob = { id, merchantId, total, processed: 0, status: 'queued', proposals: [] }
  all[id] = job
  writeAll(all)
  return job
}

export function updateJob(job: BulkJob){ const all=readAll(); all[job.id]=job; writeAll(all); return job }
export function getJob(id: string){ return readAll()[id] || null }


