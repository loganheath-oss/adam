import type { Metadata } from "next";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";
import { PageTransition } from "@/components/page-transition";

export const metadata: Metadata = {
  title: "ADAM · Upwork Paid Acquisition",
  description: "AI-assisted ad creative production for Upwork Paid Acquisition.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <SiteNav />
        <main className="mx-auto max-w-[1080px] px-6 py-12">
          <PageTransition>{children}</PageTransition>
        </main>
      </body>
    </html>
  );
}
