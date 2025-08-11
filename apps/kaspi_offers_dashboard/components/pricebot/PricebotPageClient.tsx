'use client'
import { useEffect, useState } from 'react'
import StoreSelector from '@/components/pricebot/StoreSelector'
import ImportExportBar from '@/components/pricebot/ImportExportBar'
import GlobalIgnore from '@/components/pricebot/GlobalIgnore'
import PricebotTable from '@/components/pricebot/PricebotTable'
import PricebotPanel from '@/components/PricebotPanel'
import { usePricebotStore } from '@/lib/pricebot/store'

export default function PricebotPageClient() {
  const [storeId, setStoreId] = useState<string>('')
  const loadOffers = usePricebotStore(s=>s.loadOffers)
  useEffect(()=>{
    (async()=>{
      const res = await fetch('/api/pricebot/stores', { cache:'no-store' })
      const js = await res.json()
      const id = (js?.items?.[0]?.id) || ''
      setStoreId(id)
      await loadOffers(id)
    })()
  },[])
  return (
    <main className="min-h-screen max-w-7xl mx-auto p-4 md:p-6 space-y-4">
      <header className="sticky top-0 z-10 bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/60 flex items-center justify-between py-3">
        <h1 className="text-2xl md:text-3xl font-bold">Pricebot {storeId ? `(Store ${storeId})` : ''}</h1>
        <div className="flex items-center gap-3">
          <StoreSelector onChange={setStoreId} />
          <ImportExportBar storeId={storeId} />
        </div>
      </header>
      <PricebotPanel storeId={storeId} />
      <GlobalIgnore storeId={storeId} />
      <PricebotTable storeId={storeId} />
    </main>
  )
}


