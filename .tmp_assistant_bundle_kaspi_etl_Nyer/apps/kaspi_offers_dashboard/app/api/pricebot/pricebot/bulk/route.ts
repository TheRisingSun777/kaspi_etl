import { NextResponse } from 'next/server'
import { BulkInputSchema } from '@/server/lib/validation'
import { createJob, getJob, updateJob } from '@/server/db/pricebot.jobs'
import { getSettings } from '@/server/db/pricebot.settings'

export async function POST(req: Request) {
  try {
    const body = await req.json().catch(()=>({}))
    const parsed = BulkInputSchema.safeParse(body)
    if (!parsed.success) return NextResponse.json({ ok:false, code:'bad_input', message:'Invalid bulk input', details: parsed.error.flatten() }, { status: 400 })
    const { storeId, merchantId, skus } = parsed.data as any
    const mId = String(storeId || merchantId || '')
    if (!mId) return NextResponse.json({ ok:false, code:'bad_input', message:'merchant/store required' }, { status: 400 })
    const list: string[] = Array.isArray(skus) && skus.length ? skus : Object.keys(getSettings(mId).sku || {})
    const job = createJob(mId, list.length)
    // Fire-and-forget background processing (naive)
    queueMicrotask(async()=>{
      try {
        job.status = 'running'; updateJob(job)
        for (const sku of list) {
          const st = getSettings(mId).sku[sku]
          if (!st) { job.processed++; updateJob(job); continue }
          let target = st.minPrice || 0
          if (st.maxPrice) target = Math.min(st.maxPrice, target)
          job.proposals.push({ sku, target })
          job.processed++
          updateJob(job)
        }
        job.status = 'done'; job.summary = { proposed: job.proposals.length }; updateJob(job)
      } catch (e:any) { job.status='error'; job.error=String(e?.message||e); updateJob(job) }
    })
    return NextResponse.json({ ok:true, jobId: job.id })
  } catch (e:any) {
    return NextResponse.json({ ok:false, code:'server_error', message:String(e?.message||e) }, { status: 500 })
  }
}

export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const id = String(searchParams.get('jobId') || '')
  const job = id ? getJob(id) : null
  return NextResponse.json(job ? { ok:true, job } : { ok:false, code:'not_found' }, { status: job ? 200 : 404 })
}


