import { NextResponse } from 'next/server'

// Minimal in-memory ring buffer for demo
const LOGS: string[] = []
export function pushLog(line: string) {
  LOGS.push(new Date().toISOString() + ' ' + line)
  if (LOGS.length > 200) LOGS.shift()
}

export async function GET() {
  return NextResponse.json({ logs: LOGS.slice(-100) })
}


