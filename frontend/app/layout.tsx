import type { Metadata } from "next";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";

export const metadata: Metadata = {
  title: "MatchLambda — Football Quantitative Terminal & AI Picks",
  description: "Dixon–Coles Poisson probability modeling, Shin de-juicing, +EV value scanner, and smart parlays.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#080c14] text-slate-100 antialiased">
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
