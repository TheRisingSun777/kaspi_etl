import type { VariantInfo } from '@/lib/types'
import SellersTable from './SellersTable'

export default function VariantCard({ variant }: { variant: VariantInfo }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-gray-500">Variant</div>
          <div className="text-lg font-semibold">{variant.label}</div>
          <div className="text-xs text-gray-500 mt-1">Product ID: {variant.productId}</div>
        </div>
        <div className="text-sm text-gray-500">Sellers: {variant.sellersCount}</div>
      </div>
      <div className="mt-3">
        <SellersTable sellers={variant.sellers} />
      </div>
    </div>
  )
}


