import { NextResponse } from 'next/server'
import { listRules } from '@/server/db/rules'

export async function POST() {
  // For now, respond with a placeholder; wiring a full scheduler separately
  const rules = listRules()
  return NextResponse.json({ ok: true, queued: rules.length })
}


