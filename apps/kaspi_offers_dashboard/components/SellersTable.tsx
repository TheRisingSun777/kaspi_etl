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
            <th className="p-2">Delivery</th>
          </tr>
        </thead>
        <tbody>
          {sellers.map((s, i) => (
            <tr key={i} className="border-t border-gray-200/70 dark:border-gray-700/60">
              <td className="p-2">{s.name}</td>
              <td className="p-2">{new Intl.NumberFormat('en-US').format(s.price)}</td>
              <td className="p-2">{s.deliveryDate}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}


