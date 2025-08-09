import type { AnalyzeResult } from '@/lib/types'

export default function AnalyticsPanel({ data }: { data: AnalyzeResult }) {
  const a = data.analytics || {}
  return (
    <div className="card p-4">
      <div className="text-sm text-gray-500 mb-2">Analytics</div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
        <div>
          <div className="text-text-secondary text-xs">Avg Spread</div>
          <div className="font-medium">{a.avgSpread ?? '—'}</div>
        </div>
        <div>
          <div className="text-text-secondary text-xs">Median Spread</div>
          <div className="font-medium">{a.medianSpread ?? '—'}</div>
        </div>
        <div>
          <div className="text-text-secondary text-xs">Max Spread</div>
          <div className="font-medium">{a.maxSpread ?? '—'}</div>
        </div>
        <div>
          <div className="text-text-secondary text-xs">Bot Share</div>
          <div className="font-medium">{typeof a.botShare === 'number' ? Math.round(a.botShare * 100) + '%' : '—'}</div>
        </div>
        <div>
          <div className="text-text-secondary text-xs">Attractiveness</div>
          <div className="font-medium">{a.attractivenessIndex ?? '—'}</div>
        </div>
      </div>
    </div>
  )
}


