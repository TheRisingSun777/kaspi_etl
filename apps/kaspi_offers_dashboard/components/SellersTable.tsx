import type { SellerInfo } from '@/lib/types'

export default function SellersTable({ sellers }: { sellers: SellerInfo[] }) {
  if (!sellers?.length) {
    return <div className="text-sm text-gray-500">No sellers</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="text-left text-gray-500">
          <tr>
            <th className="p-2">Seller</th>
            <th className="p-2">Price</th>
            <th className="p-2">Δ vs Min</th>
            <th className="p-2">PriceBot?</th>
            <th className="p-2">Delivery</th>
          </tr>
        </thead>
        <tbody>
          {(() => {
            const min = Math.min(...sellers.map(s => s.price))
            return sellers.map((s, i) => {
              const delta = s.price - min
              const isBot = s.isPriceBot ? 'Yes' : 'No'
              const isMin = s.price === min
              return (
                <tr key={i} className={`border-t border-gray-200/70 dark:border-gray-700/60 ${isMin ? 'bg-white/40 dark:bg-white/5' : ''}`}>
                  <td className="p-2">{s.name}</td>
                  <td className="p-2">{new Intl.NumberFormat('en-US').format(s.price)}</td>
                  <td className="p-2">{delta ? `+${delta}` : '—'}</td>
                  <td className="p-2">{isBot}</td>
                  <td className="p-2">{s.deliveryDate || ''}</td>
                </tr>
              )
            })
          })()}
        </tbody>
      </table>
    </div>
  )
}


