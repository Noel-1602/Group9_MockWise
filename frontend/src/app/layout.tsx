import type { Metadata } from "next";
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
      <body>{children}</body>
    </html>
  );
}

