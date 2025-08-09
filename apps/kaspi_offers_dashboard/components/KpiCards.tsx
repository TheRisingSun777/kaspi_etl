import type { AnalyzeResponse } from '@/lib/types'

interface Props {
  data: AnalyzeResponse | null
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-gray-500">{label}</div>
      <div className="text-2xl font-semibold mt-1">{value || '—'}</div>
    </div>
  )
}

export default function KpiCards({ data }: Props) {
  const totalVariants = data?.variants.length ?? 0
  const totalSellers = data?.variants.reduce((acc, v) => acc + (v.sellers?.length || 0), 0) ?? 0

  // fastest delivery (min date)
  let fastest = '—'
  if (data?.variants) {
    const dates = data.variants.flatMap((v) => v.sellers.map((s) => s.deliveryDate)).filter(Boolean)
    if (dates.length) {
      fastest = dates.sort()[0]
    }
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Kpi label="Product Name" value={data?.productName || '—'} />
      <Kpi label="Total Variants" value={String(totalVariants)} />
      <Kpi label="Total Sellers" value={String(totalSellers)} />
      <Kpi label="Fastest Delivery" value={fastest} />
    </div>
  )
}


