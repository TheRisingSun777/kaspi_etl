import PricebotTable from '@/components/pricebot/PricebotTable'
import GlobalIgnore from '@/components/pricebot/GlobalIgnore'
import ImportExportBar from '@/components/pricebot/ImportExportBar'
import dynamic from 'next/dynamic'
const StoreSelector = dynamic(() => import('@/components/pricebot/StoreSelector'), { ssr: false })

export const dynamic = 'force-dynamic'

export default function PricebotPage() {
  return (
    <main className="min-h-screen max-w-7xl mx-auto p-4 md:p-6 space-y-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl md:text-3xl font-bold">Pricebot (Store 30141222)</h1>
        <div className="flex items-center gap-3">
          <StoreSelector onChange={()=>{ /* todo: filter data by store */ }} />
          <ImportExportBar />
        </div>
      </header>
      <GlobalIgnore />
      <PricebotTable />
    </main>
  )
}


