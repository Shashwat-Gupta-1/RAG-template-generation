import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/AuthProvider";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RAG Template Generation",
  description: "Generate promotional posters",
};

import Sidebar from "@/components/Sidebar";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${inter.variable} antialiased bg-[#0a0a0a] text-white min-h-screen`}
      >
        <AuthProvider>
          <div className="flex w-full min-h-screen">
            <Sidebar />
            <main className="flex-1 w-full ml-[60px] md:ml-[220px] transition-all duration-300">
              {children}
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
