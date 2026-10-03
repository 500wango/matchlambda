"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Zap, TrendingUp, DollarSign, Filter, Sliders, Shield, ArrowUpRight, CheckCircle2, ChevronRight, Activity } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface AlphaScannerViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
  onSelectMatch: (matchId: string) => void;
}

export const AlphaScannerView: React.FC<AlphaScannerViewProps> = ({
  isAnalyst,
  onOpenPricing,
  onSelectMatch,
}) => {
  const { lang, t } = useI18n();
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Staking Inputs
  const [bankroll, setBankroll] = useState<number>(5000);
  const [strategy, setStrategy] = useState<string>("HALF_KELLY");
  const [minEv, setMinEv] = useState<number>(0.04);
  const [leagueFilter, setLeagueFilter] = useState<string>("ALL");

  const fetchSignals = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `/alpha/scanner?min_ev=${minEv}&bankroll=${bankroll}&strategy=${strategy}&limit=40`;
      if (leagueFilter && leagueFilter !== "ALL") {
        url += `&league_id=${leagueFilter}`;
      }
      const data = await apiRequest<any>(url);
      setSignals(data.signals || []);
    } catch (err: any) {
      setError(err?.message || (lang === "zh" ? "无法加载量化信号。" : "Failed to scan alpha signals."));
    } finally {
      setLoading(false);
    }
  }, [bankroll, strategy, minEv, leagueFilter, lang]);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  const isEn = lang === "en";

  return (
    <div className="space-y-6">
      {/* Hero Control Console */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 sm:p-7 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-3">
              <Zap className="w-3.5 h-3.5" />
              <span>{isEn ? "Real-Time +EV Arbitrage & Mispricing Scanner" : "实时 +EV 套利与市场定价偏差扫描雷达"}</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>⚡ {t("scanner.title")}</span>
            </h2>
            <p className="text-xs sm:text-sm text-gray-400 mt-2 max-w-2xl leading-relaxed">
              {t("scanner.subtitle")}
            </p>
          </div>

          {/* Quick Bankroll & Strategy Form */}
          <div className="bg-[#090d16] border border-gray-800/80 rounded-xl p-4 flex flex-wrap sm:flex-nowrap items-center gap-4">
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {t("scanner.bankroll")}
              </label>
              <div className="relative">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-xs">$</span>
                <input
                  type="number"
                  value={bankroll}
                  onChange={(e) => setBankroll(Math.max(10, Number(e.target.value)))}
                  className="w-28 pl-6 pr-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs font-bold focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {t("scanner.strategy")}
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="py-1.5 px-2.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs focus:border-blue-500 focus:outline-none"
              >
                <option value="HALF_KELLY">{isEn ? "Half-Kelly (0.5x)" : "半凯利 (Half-Kelly 0.5x)"}</option>
                <option value="QUARTER_KELLY">{isEn ? "Quarter-Kelly (0.25x)" : "四分之一凯利 (0.25x 保守)"}</option>
                <option value="FULL_KELLY">{isEn ? "Full-Kelly (1.0x)" : "全凯利 (Full-Kelly 1.0x 进取)"}</option>
                <option value="FIXED_1_PCT">{isEn ? "Fixed 1.0% Flat" : "固定 1.0% 单注"}</option>
                <option value="FLAT_UNIT">{isEn ? "Flat Unit (1.5%)" : "固定平注 (Flat Unit)"}</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {t("scanner.minEv")}
              </label>
              <select
                value={minEv}
                onChange={(e) => setMinEv(Number(e.target.value))}
                className="py-1.5 px-2.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs focus:border-blue-500 focus:outline-none"
              >
                <option value={0.02}>EV ≥ +2.0%</option>
                <option value={0.04}>EV ≥ +4.0% ({isEn ? "Recommended" : "建议"})</option>
                <option value={0.08}>EV ≥ +8.0% ({isEn ? "High Value" : "高价值"})</option>
                <option value={0.15}>EV ≥ +15.0% ({isEn ? "Extreme Alpha" : "极高偏差"})</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Signals Grid / Table */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 sm:p-5 border-b border-gray-800 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              {isEn ? "Active +EV Market Feed" : "当前活跃 +EV 信号池"}
            </span>
            <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
              {t("scanner.signalsFound", { count: signals.length })}
            </span>
          </div>

          {/* League quick filter */}
          <div className="flex items-center space-x-1.5 overflow-x-auto text-xs font-mono">
            {["ALL", "TOP5", "EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1"].map((l) => (
              <button
                key={l}
                onClick={() => setLeagueFilter(l)}
                className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
                  leagueFilter === l
                    ? "bg-blue-600 text-white font-bold"
                    : "bg-[#090d16] text-gray-400 hover:text-white border border-gray-800"
                }`}
              >
                {l === "ALL" ? (isEn ? "All" : "全部") : l === "TOP5" ? (isEn ? "Top 5" : "五大联赛") : l}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-gray-400 font-mono">
              {isEn ? "Scanning live market lines and computing Poisson expectations..." : "正在扫描全网 17 大联赛盘口并计算泊松正期望值..."}
            </p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-400 font-mono text-xs">{error}</div>
        ) : signals.length === 0 ? (
          <div className="py-16 text-center text-gray-400">
            <p className="text-sm">{t("scanner.noSignals")}</p>
            <p className="text-xs text-gray-500 mt-1">
              {isEn ? "Try lowering the minimum EV threshold or expanding league scope." : "您可以尝试调低最低 EV 门槛或扩大联赛范围。"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-gray-800/80 bg-[#0a0e1a] text-gray-400 text-[11px]">
                  <th className="py-3 px-4">{t("scanner.grade")}</th>
                  <th className="py-3 px-4">{t("scanner.match")} / {t("scanner.league")}</th>
                  <th className="py-3 px-4">{t("scanner.selection")}</th>
                  <th className="py-3 px-4">{t("scanner.marketOdds")} vs {t("scanner.fairOdds")}</th>
                  <th className="py-3 px-4">{t("scanner.ev")}</th>
                  <th className="py-3 px-4">{t("scanner.suggestedStake")}</th>
                  <th className="py-3 px-4">{t("scanner.expectedProfit")}</th>
                  <th className="py-3 px-4 text-right">{t("scanner.action")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800/60">
                {signals.map((sig) => {
                  return (
                    <tr
                      key={sig.signal_id}
                      className="hover:bg-blue-950/20 transition group"
                    >
                      {/* Grade */}
                      <td className="py-3.5 px-4">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[11px] font-black ${
                            sig.confidence_grade === "A+"
                              ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                              : sig.confidence_grade === "A"
                              ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                              : "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                          }`}
                        >
                          {sig.confidence_grade}
                        </span>
                      </td>

                      {/* Match & League */}
                      <td className="py-3.5 px-4">
                        <div className="font-sans font-bold text-white text-sm">
                          {sig.home_team} vs {sig.away_team}
                        </div>
                        <div className="text-[11px] text-gray-400 flex items-center space-x-2 mt-0.5">
                          <span className="text-blue-400 font-bold">{sig.league_id}</span>
                          <span>·</span>
                          <span>
                            {new Date(sig.match_date).toLocaleDateString(isEn ? "en-US" : "zh-CN")} {new Date(sig.match_date).toLocaleTimeString(isEn ? "en-US" : "zh-CN", { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      </td>

                      {/* Selection */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-emerald-400 text-sm">
                          {sig.selection_label}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {isEn ? "Bookmaker" : "庄家"}: {sig.bookmaker}
                        </div>
                      </td>

                      {/* Odds */}
                      <td className="py-3.5 px-4">
                        <div className="text-white font-bold text-sm">
                          {sig.market_odds.toFixed(2)}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {isEn ? "Fair" : "公允"}: {sig.fair_odds.toFixed(2)} ({isEn ? "Win" : "胜率"} {(sig.model_prob * 100).toFixed(1)}%)
                        </div>
                      </td>

                      {/* EV */}
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded font-black text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                          +{sig.ev_pct}%
                        </span>
                        <div className="text-[10px] text-gray-400 mt-0.5">
                          Edge: +{sig.edge_pct}%
                        </div>
                      </td>

                      {/* Suggested Stake */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white text-sm">
                          ${sig.suggested_stake}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {sig.half_kelly_pct}% {isEn ? "Bankroll" : "本金"}
                        </div>
                      </td>

                      {/* Expected Profit */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-emerald-400 text-sm">
                          +${sig.expected_profit}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {isEn ? "Expected EV" : "按模型期望"}
                        </div>
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() => onSelectMatch(sig.match_id)}
                          className="px-3 py-1.5 rounded-lg bg-blue-600/20 hover:bg-blue-600 text-blue-400 hover:text-white transition text-xs font-semibold inline-flex items-center"
                        >
                          {isEn ? "Quant Dive" : "深度分析"} <ChevronRight className="w-3.5 h-3.5 ml-1" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
