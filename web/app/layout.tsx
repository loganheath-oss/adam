import type { Metadata } from "next";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";

export const metadata: Metadata = {
  title: "ADAM",
  description: "AI-assisted ad creative production for Upwork Paid Acquisition.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <SiteNav />
        <main className="mx-auto max-w-6xl px-6 py-12">{children}</main>
      </body>
    </html>
  );
}
