import { NextResponse } from 'next/server'
import { getJob, updateJob } from '@/server/db/pricebot.jobs'
import { updatePriceBySku } from '@/server/merchant/client'
import { addRun } from '@/server/db/pricebot.runs'

export async function POST(_req: Request, { params }: { params: { jobId: string } }) {
  try {
    const id = params.jobId
    const job = getJob(id)
    if (!job) return NextResponse.json({ ok:false, code:'not_found' }, { status:404 })
    if (job.status !== 'done') return NextResponse.json({ ok:false, code:'not_ready' }, { status:400 })
    let applied = 0
    for (const p of job.proposals) {
      try {
        await updatePriceBySku({ sku: p.sku, newPrice: p.target })
        addRun({ ts: new Date().toISOString(), merchantId: job.merchantId, storeId: job.merchantId, mode: 'apply', count: 1, avgDelta: (p.target - (p.ourPrice||0)), applied: true })
        applied++
      } catch {}
    }
    job.summary = { ...(job.summary||{}), applied }
    updateJob({ ...job })
    return NextResponse.json({ ok:true, applied })
  } catch (e:any) {
    return NextResponse.json({ ok:false, code:'server_error', message:String(e?.message||e) }, { status:500 })
  }
}


