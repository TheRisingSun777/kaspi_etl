import type { AnalyzeResult } from '@/lib/types'

export default function ModelInfo({ data }: { data: AnalyzeResult }) {
  const sizes = data.attributes?.sizesAll || []
  const colors = data.attributes?.colorsAll || []
  const variantMap = data.variantMap || {}
  return (
    <div className="card p-4 flex items-start gap-4">
      {data.productImageUrl ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={data.productImageUrl} alt="product" className="w-28 h-28 object-cover rounded-lg border border-gray-200 dark:border-gray-700" />
      ) : null}
      <div className="flex-1">
        <div className="text-sm text-gray-500">Model</div>
        <div className="text-lg font-semibold">{data.productName}</div>
        <div className="mt-2 flex flex-col gap-2 text-sm">
          {colors.length > 0 && (
            <div>
              <span className="text-gray-500">Colors: </span>
              {colors.join(', ')}
            </div>
          )}
          {sizes.length > 0 && (
            <div className="overflow-x-auto">
              <span className="text-gray-500">Sizes: </span>
              <div className="mt-1 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-1">
                {Object.entries(variantMap).map(([pid, label]) => (
                  <div key={pid} className="text-xs text-gray-300">
                    <span className="text-gray-500">{label}</span>
                    <span className="ml-2 opacity-70">({pid})</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {typeof data.ratingCount === 'number' && (
            <div>
              <span className="text-gray-500">Ratings: </span>
              {data.ratingCount}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


