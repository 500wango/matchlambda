"use client";

import React from "react";
import { Shield, Zap, User as UserIcon, LogOut, ChevronRight } from "lucide-react";

interface NavbarProps {
  user: { email: string; effective_plan: string; plan_expires_at?: string } | null;
  onOpenAuth: () => void;
  onOpenPricing: () => void;
  onLogout: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  user,
  onOpenAuth,
  onOpenPricing,
  onLogout,
}) => {
  const isAnalyst = user?.effective_plan === "ANALYST";

  return (
    <header className="border-b border-gray-800 bg-[#0d121f]/90 backdrop-blur sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-blue-500/20">
            λ
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-extrabold text-xl tracking-tight text-white">MatchLambda</span>
              <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20 px-1.5 py-0.5 rounded font-mono font-medium">
                v1.3.0
              </span>
            </div>
            <p className="text-xs text-gray-400 font-mono">EPL Dixon–Coles Probability Engine</p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {user ? (
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2 bg-gray-900 border border-gray-800 px-3 py-1.5 rounded-lg text-xs">
                <span className="text-gray-400 font-mono">{user.email}</span>
                {isAnalyst ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <Shield className="w-3 h-3 mr-1" /> ANALYST
                  </span>
                ) : (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-gray-700/50 text-gray-300">
                    FREE
                  </span>
                )}
              </div>

              {!isAnalyst && (
                <button
                  onClick={onOpenPricing}
                  className="flex items-center text-xs font-semibold bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white px-3.5 py-2 rounded-lg transition shadow-md shadow-blue-600/20"
                >
                  <Zap className="w-3.5 h-3.5 mr-1" />
                  Upgrade Pass
                </button>
              )}

              <button
                onClick={onLogout}
                className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition"
                title="Log out"
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
                Log in
              </button>
              <button
                onClick={onOpenPricing}
                className="flex items-center text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white px-3.5 py-2 rounded-lg transition shadow-md shadow-blue-500/20"
              >
                <Zap className="w-3.5 h-3.5 mr-1" />
                Get Analyst Pass
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
