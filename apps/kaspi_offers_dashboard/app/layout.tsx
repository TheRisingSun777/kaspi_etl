import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Kaspi Offers Insight',
  description: 'Analyze Kaspi product variants and sellers',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}


