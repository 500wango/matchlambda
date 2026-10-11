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
  // Keep the SSR default ("zh"), then align <html lang> with the stored /
  // browser language before first paint so English users are not announced as
  // Chinese by assistive tech. suppressHydrationWarning covers the attribute
  // this script may rewrite before React hydrates (same pattern as next-themes).
  const langSyncScript = `(function(){try{var l=localStorage.getItem("matchlambda_lang");if(l!=="en"&&l!=="zh"){l=(navigator.language||"").toLowerCase().indexOf("en")===0?"en":"zh";}document.documentElement.lang=l;}catch(e){}})();`;

  return (
    <html lang="zh" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: langSyncScript }} />
      </head>
      <body className="bg-[#080c14] text-slate-100 antialiased">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-blue-600 focus:px-3 focus:py-2 focus:text-sm focus:text-white"
        >
          跳到主要内容
        </a>
        <I18nProvider>{children}</I18nProvider>
      </body>
    </html>
  );
}
