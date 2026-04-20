import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'STR Feasibility Calculator',
  description: 'Professional short-term rental feasibility and risk analysis',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-slate-50 min-h-screen`}>
        <header className="bg-[#0F172A] text-white px-6 py-4 shadow-lg">
          <div className="max-w-6xl mx-auto flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-[#AF7225] rounded-lg flex items-center justify-center text-white font-bold text-sm">STR</div>
              <span className="font-semibold text-lg tracking-tight">Feasibility Calculator</span>
            </div>
            <span className="text-slate-400 text-sm">Powered by Inside Airbnb + Monte Carlo</span>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">
          {children}
        </main>
      </body>
    </html>
  )
}
