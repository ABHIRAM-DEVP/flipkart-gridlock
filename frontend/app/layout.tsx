import type { Metadata } from "next";
import "./globals.css";
import { SoftPillNav } from "@/components/SoftPillNav";
import { ConnectivityBanner } from "@/components/ConnectivityBanner";

export const metadata: Metadata = {
  title: "Astram - Incident Prediction System",
  description: "Advanced ML-driven orchestration for event prediction.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Reenie+Beanie&display=swap" rel="stylesheet" />
      </head>
      <body className="min-h-screen relative">
        <div className="grain-overlay" />

        <SoftPillNav />
        <ConnectivityBanner />
        
        <main className="relative z-10 pt-24 pb-12 px-4 sm:px-6 max-w-7xl mx-auto">
          {children}
        </main>
      </body>
    </html>
  );
}
