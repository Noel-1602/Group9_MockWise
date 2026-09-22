import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "MockWise",
  description: "Speech-to-Speech AI Mock Interview Platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased flex flex-col">
        <header className="sticky top-0 z-50 bg-white border-b border-slate-200">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center">
            <Link
              href="/"
              className="text-xl font-bold tracking-tight text-slate-900 hover:text-indigo-600 transition-colors"
            >
              MockWise
            </Link>
          </div>
        </header>
        <main className="flex-1 w-full px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
      </body>
    </html>
  );
}
