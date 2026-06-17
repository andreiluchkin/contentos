import type { Metadata } from "next"
import "./globals.css"
import { Providers } from "./providers"
import { Sidebar } from "@/components/layout/Sidebar"
import { MobileNav } from "@/components/layout/MobileNav"

export const metadata: Metadata = {
  title: "ContentOS",
  description: "Content Production Operating System",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="ru">
      <body>
        <Providers>
          <div className="flex h-screen overflow-hidden">
            {/* Desktop sidebar */}
            <Sidebar />

            {/* Main content */}
            <main className="flex-1 overflow-auto bg-canvas pb-20 md:pb-0">
              {children}
            </main>
          </div>

          {/* Mobile bottom nav */}
          <MobileNav />
        </Providers>
      </body>
    </html>
  )
}
