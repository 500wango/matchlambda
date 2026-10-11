"use client";

import React from "react";
import Link from "next/link";
import { Shield, Zap, User as UserIcon, LogOut, ChevronRight, Globe, Settings } from "lucide-react";
import { useI18n } from "@/lib/i18n";

interface NavbarProps {
  user: { email: string; effective_plan: string; plan_expires_at?: string; is_admin?: boolean } | null;
  onOpenAuth: () => void;
  onOpenPricing: () => void;
  onLogout: () => void;
  onLogoClick?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  onOpenAuth,
  onOpenPricing,
  onLogout,
  onLogoClick,
}) => {
  const { lang, toggleLang, t } = useI18n();
  const isAnalyst = user?.effective_plan === "ANALYST";

  return (
    <header aria-label="Site" className="border-b border-gray-800 bg-[#0d121f]/90 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <Link
          href="/"
          onClick={onLogoClick}
          className="flex items-center space-x-3 group cursor-pointer hover:opacity-95 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 rounded-lg p-0.5"
          title={lang === "zh" ? "返回首页" : "Return to Home"}
        >
          <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-blue-500/20 group-hover:bg-blue-500 transition">
            λ
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-xl tracking-tight text-white group-hover:text-blue-300 transition">
                {t("nav.brand")}
              </span>
              <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-mono font-medium">
                {t("nav.version")}
              </span>
            </div>
            <p className="text-xs text-gray-400 font-mono hidden sm:block">
              {t("nav.subtitle")}
            </p>
          </div>
        </Link>

        <div className="flex items-center space-x-3">
          {/* Language Switcher Toggle */}
          <button
            onClick={toggleLang}
            className="flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg bg-gray-900 border border-gray-800 hover:border-gray-700 text-xs text-gray-300 hover:text-white transition font-mono"
            title={lang === "zh" ? "Switch to English" : "切换为简体中文"}
            aria-label={lang === "zh" ? "Switch to English" : "切换为简体中文"}
          >
            <Globe className="w-3.5 h-3.5 text-blue-400" />
            <span className="font-bold">{lang === "zh" ? "EN" : "中"}</span>
          </button>

          {user ? (
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-lg text-xs">
                <span className="text-gray-400 font-mono truncate max-w-[120px] sm:max-w-[180px]">
                  {user.email}
                </span>
                {isAnalyst ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Shield className="w-3 h-3 mr-1" /> {t("nav.analyst")}
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-700/50 text-gray-300">
                    {t("nav.free")}
                  </span>
                )}
              </div>

              {user.is_admin && (
                <Link
                  href="/admin"
                  className="flex items-center space-x-1 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-semibold transition"
                  title={t("nav.admin")}
                  aria-label={t("nav.admin").replace(/^⚙️\s*/, "")}
                >
                  <Settings className="w-3.5 h-3.5" />
                  <span>{t("nav.admin")}</span>
                </Link>
              )}

              {!isAnalyst && (
                <button
                  onClick={onOpenPricing}
                  className="flex items-center text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-3.5 py-2 rounded-lg transition shadow-md shadow-blue-600/20"
                >
                  <Zap className="w-3.5 h-3.5 mr-1" />
                  {t("nav.upgrade")}
                </button>
              )}

              <button
                onClick={onLogout}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition"
                title={t("nav.logout")}
                aria-label={t("nav.logout")}
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center space-x-3">
              <button
                onClick={onOpenAuth}
                className="text-xs font-medium text-gray-300 hover:text-white px-3 py-2 transition"
              >
                {t("nav.login")}
              </button>
              <button
                onClick={onOpenPricing}
                className="flex items-center text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-2 rounded-lg transition shadow-md shadow-blue-500/20"
              >
                <Zap className="w-3.5 h-3.5 mr-1" />
                {t("nav.getPass")}
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
