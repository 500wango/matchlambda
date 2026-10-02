import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MatchLambda — EPL Dixon–Coles Probability & Market Intelligence",
  description: "Reproducible pre-match Premier League probabilities, Shin de-juicing, and value scanner.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080c14] text-slate-100 antialiased">{children}</body>
    </html>
  );
}
