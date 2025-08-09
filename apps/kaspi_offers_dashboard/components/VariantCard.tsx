import type { VariantInfo } from '@/lib/types'
import SellersTable from './SellersTable'

export default function VariantCard({ variant }: { variant: VariantInfo }) {
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm text-gray-500">Variant</div>
          <div className="text-lg font-semibold flex items-center gap-2">
            <span className="text-xs text-gray-500">{variant.productId}</span>
            <span>{variant.label}</span>
            {variant.variantColor && (
              <span className="text-xs rounded-full px-2 py-0.5 bg-border text-text-secondary border" title="Color">
                {variant.variantColor}
              </span>
            )}
          </div>
          <div className="text-xs text-gray-500 mt-1">Product ID: {variant.productId}</div>
          {variant.rating && (typeof variant.rating.avg !== 'undefined' || typeof variant.rating.count !== 'undefined') && (
            <div className="text-xs text-gray-500 mt-1">★ {variant.rating.avg ?? '—'} · {variant.rating.count ?? 0}</div>
          )}
        </div>
        <div className="text-sm text-gray-500">Sellers: {variant.sellersCount}</div>
      </div>
      <div className="mt-3">
        <SellersTable sellers={variant.sellers} />
        {variant.stats && (
          <div className="mt-2 text-xs text-gray-500 flex flex-wrap gap-3">
            <div>min: {variant.stats.min ?? '—'}</div>
            <div>median: {variant.stats.median ?? '—'}</div>
            <div>max: {variant.stats.max ?? '—'}</div>
            <div>spread: {variant.stats.spread ?? '—'}</div>
            <div>σ: {variant.stats.stddev ? variant.stats.stddev.toFixed(1) : '—'}</div>
          </div>
        )}
      </div>
    </div>
  )
}


