import type { Metadata } from "next";
import "../src/index.css";

export const metadata: Metadata = {
  title: "MS Fincap AI Intelligence - Admin Dashboard",
  description: "Admin Intelligence Dashboard for MS Fincap with user directory, AI interaction logs, asset library, and poster template presets.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased font-sans bg-[#F4F6FA] text-[#1b1b1e]">
        {children}
      </body>
    </html>
  );
}
