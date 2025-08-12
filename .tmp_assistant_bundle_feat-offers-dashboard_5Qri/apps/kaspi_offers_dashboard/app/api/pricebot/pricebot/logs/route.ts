import { NextResponse } from 'next/server'

// Minimal in-memory ring buffer for demo
const LOGS: string[] = []

export const runtime = 'nodejs'

export async function GET() {
  return NextResponse.json({ logs: LOGS.slice(-100) })
}


