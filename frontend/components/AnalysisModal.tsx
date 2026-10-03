"use client";

import React, { useState, useEffect } from "react";
import { X, Clock, AlertTriangle, Activity, Database, CheckCircle, Flame, Layers, Calculator, ShieldCheck, TrendingUp, BarChart2 } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface AnalysisModalProps {
  matchId: string | null;
  fixture?: any;
  onClose: () => void;
}

export const AnalysisModal: React.FC<AnalysisModalProps> = ({ matchId, fixture, onClose }) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("1X2");

  // Custom bankroll calculator inside modal
  const [calcBankroll, setCalcBankroll] = useState<number>(5000);

  // Esc key listener and body scroll lock
  useEffect(() => {
    if (!matchId) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);

    const origOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = origOverflow;
    };
  }, [matchId, onClose]);

  // Fetch analysis data
  useEffect(() => {
    if (!matchId) return;

    let isMounted = true;
    setLoading(true);
    setError(null);

    apiRequest<any>(`/matches/${matchId}/analysis`)
      .then((res) => {
        if (isMounted) setData(res);
      })
      .catch((err) => {
        if (isMounted) setError(err.message || "Failed to load match analysis.");
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [matchId]);

  if (!matchId) return null;

  const deriv = data?.derivatives;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 md:p-6 bg-black/85 backdrop-blur-md"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-[#0f1523] border border-gray-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Sticky Header with visible close button */}
        <div className="flex items-center justify-between px-5 sm:px-7 py-4 border-b border-gray-800 bg-[#0d121e] z-20 flex-shrink-0">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex-shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-base sm:text-lg font-bold text-white truncate">
                  {fixture ? `${fixture.home_team.name} vs ${fixture.away_team.name}` : "Dixon–Coles 深度量化模型分析"}
                </h3>
                {fixture && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex-shrink-0">
                    {fixture.league_id}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 font-mono truncate">
                {fixture ? `${new Date(fixture.match_date).toLocaleString()} · ` : ""}
                ID: {matchId}
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 hover:text-white transition text-xs font-semibold flex-shrink-0 ml-3 border border-gray-700 shadow-sm"
            aria-label={isEn ? "Close modal" : "关闭窗口"}
          >
            <span>{isEn ? "Close" : "关闭"}</span>
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Modal Subnav Tabs */}
        <div className="flex items-center space-x-1 px-5 sm:px-7 pt-3 pb-2 border-b border-gray-800/80 bg-[#0a0e18] overflow-x-auto text-xs font-mono scrollbar-none flex-shrink-0">
          {[
            { id: "1X2", label: isEn ? "1X2 & EV Edge" : "1X2 胜平负与 EV" },
            { id: "TOTALS", label: isEn ? "Totals (Over/Under)" : "大小球 (Totals O/U)" },
            { id: "BTTS", label: isEn ? "Both Teams Score (BTTS)" : "双方进球 (BTTS)" },
            { id: "HANDICAP", label: isEn ? "Asian Handicap" : "亚盘让球 (Spreads)" },
            { id: "DC", label: isEn ? "Double Chance & DNB" : "双胜彩与退款 (DC/DNB)" },
            { id: "MATRIX", label: isEn ? "6×6 Score Matrix" : "6×6 比分矩阵" },
            { id: "STAKE", label: isEn ? "💰 Kelly Calculator" : "💰 个人仓位计算器" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white font-bold shadow-md shadow-blue-500/20"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-6">
          {loading ? (
            <div className="py-24 text-center">
              <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-xs text-gray-400 font-mono">Computing Dixon–Coles probabilities & derivative markets...</p>
            </div>
          ) : error ? (
            <div className="py-16 text-center">
              <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
              <h4 className="text-white font-bold text-base mb-1">Access Restricted</h4>
              <p className="text-xs text-gray-400 max-w-sm mx-auto">{error}</p>
            </div>
          ) : data ? (
            <div className="space-y-6">
              {/* Header Status & Parameter summary */}
              <div className="border-b border-gray-800 pb-4">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-mono font-bold text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded border border-blue-500/20">
                    {data.match_id}
                  </span>

                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded font-mono font-bold flex items-center ${
                        data.data_status === "AVAILABLE"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : data.data_status === "STALE"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : "bg-red-500/10 text-red-400 border border-red-500/20"
                      }`}
                    >
                      <Activity className="w-3.5 h-3.5 mr-1" /> {data.data_status}
                    </span>
                    {data.reason && (
                      <span className="text-[11px] font-mono text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
                        {data.reason}
                      </span>
                    )}
                  </div>
                </div>

                {data.prediction && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-xs font-mono">
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Home Attack Rate (λ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.lambda_home.toFixed(3)} 期望球</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Away Attack Rate (μ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.mu_away.toFixed(3)} 期望球</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Low-score Rho (ρ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.rho.toFixed(4)} 关联度</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Expected Total Goals</span>
                      <span className="font-bold text-blue-400 text-sm">
                        {(data.prediction.lambda_home + data.prediction.mu_away).toFixed(2)} 球
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Tab 1: 1X2 Probabilities & Comparison */}
              {activeTab === "1X2" && data.comparison && data.comparison.outcomes && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Flame className="w-4 h-4 mr-1.5 text-blue-400" /> 1X2 胜平负模型概率与市场报价
                    </h4>
                    <span className="text-[11px] text-gray-400 font-mono">
                      Bookmaker: {data.comparison.bookmaker.toUpperCase()} (De-juice: {data.comparison.dejuice_method})
                    </span>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs font-mono">
                      <thead>
                        <tr className="border-b border-gray-800 text-gray-400 text-[11px]">
                          <th className="pb-2">Outcome</th>
                          <th className="pb-2">Model Prob</th>
                          <th className="pb-2">Shin Market Prob</th>
                          <th className="pb-2">Decimal Odds</th>
                          <th className="pb-2">Expected Value (EV)</th>
                          <th className="pb-2">Half-Kelly</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-800/60">
                        {data.comparison.outcomes.map((item: any) => {
                          const isValue = item.ev >= 0.05;
                          return (
                            <tr key={item.outcome} className={isValue ? "bg-emerald-500/5" : ""}>
                              <td className="py-3 font-bold text-white text-sm">{item.outcome}</td>
                              <td className="py-3 text-blue-400 font-semibold">
                                {(item.model_prob * 100).toFixed(2)}%
                              </td>
                              <td className="py-3 text-gray-400">
                                {(item.market_prob * 100).toFixed(2)}%
                              </td>
                              <td className="py-3 text-white font-bold">{item.odds.toFixed(2)}</td>
                              <td className="py-3">
                                <span
                                  className={`px-2 py-0.5 rounded font-bold ${
                                    isValue
                                      ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                      : item.ev > 0
                                      ? "text-blue-400"
                                      : "text-gray-500"
                                  }`}
                                >
                                  {item.ev > 0 ? "+" : ""}
                                  {(item.ev * 100).toFixed(2)}%
                                </span>
                              </td>
                              <td className="py-3 text-gray-300">
                                {item.half_kelly > 0 ? `${(item.half_kelly * 100).toFixed(2)}%` : "0.0%"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Tab 2: Totals Over/Under */}
              {activeTab === "TOTALS" && deriv?.totals && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                    <TrendingUp className="w-4 h-4 mr-1.5 text-emerald-400" /> 进球大小球市场概率与公允赔率分布 (Totals Over/Under)
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    {/* Over/Under 1.5 */}
                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl space-y-3 font-mono">
                      <span className="text-xs text-blue-400 font-bold block">1.5 球盘口 (Line 1.5)</span>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">大于 (Over 1.5):</span>
                        <span className="text-emerald-400 font-bold">{(deriv.totals.over_1_5.prob * 100).toFixed(1)}% ({deriv.totals.over_1_5.fair_odds})</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">小于 (Under 1.5):</span>
                        <span className="text-gray-400 font-bold">{(deriv.totals.under_1_5.prob * 100).toFixed(1)}% ({deriv.totals.under_1_5.fair_odds})</span>
                      </div>
                    </div>

                    {/* Over/Under 2.5 */}
                    <div className="bg-[#0f1523] border border-blue-500/30 p-4 rounded-xl space-y-3 font-mono shadow-lg shadow-blue-500/5">
                      <span className="text-xs text-emerald-400 font-bold block">★ 2.5 球核心盘口 (Line 2.5)</span>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">大于 (Over 2.5):</span>
                        <span className="text-emerald-400 font-bold">{(deriv.totals.over_2_5.prob * 100).toFixed(1)}% ({deriv.totals.over_2_5.fair_odds})</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">小于 (Under 2.5):</span>
                        <span className="text-gray-400 font-bold">{(deriv.totals.under_2_5.prob * 100).toFixed(1)}% ({deriv.totals.under_2_5.fair_odds})</span>
                      </div>
                    </div>

                    {/* Over/Under 3.5 */}
                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl space-y-3 font-mono">
                      <span className="text-xs text-purple-400 font-bold block">3.5 球盘口 (Line 3.5)</span>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">大于 (Over 3.5):</span>
                        <span className="text-purple-400 font-bold">{(deriv.totals.over_3_5.prob * 100).toFixed(1)}% ({deriv.totals.over_3_5.fair_odds})</span>
                      </div>
                      <div className="flex justify-between items-center text-xs">
                        <span className="text-gray-300">小于 (Under 3.5):</span>
                        <span className="text-gray-400 font-bold">{(deriv.totals.under_3_5.prob * 100).toFixed(1)}% ({deriv.totals.under_3_5.fair_odds})</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 3: BTTS */}
              {activeTab === "BTTS" && deriv?.btts && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                    <Activity className="w-4 h-4 mr-1.5 text-indigo-400" /> 双方均有进球 (Both Teams To Score - BTTS)
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono">
                    <div className="bg-[#0f1523] border border-emerald-500/30 p-5 rounded-xl flex items-center justify-between">
                      <div>
                        <span className="text-emerald-400 font-bold text-base block">BTTS: 是 (Yes)</span>
                        <span className="text-xs text-gray-400">两队在常规时间内均至少打进1球</span>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-black text-white">{(deriv.btts.yes.prob * 100).toFixed(1)}%</span>
                        <span className="text-xs text-gray-400 block">公允赔率: {deriv.btts.yes.fair_odds}</span>
                      </div>
                    </div>

                    <div className="bg-[#0f1523] border border-gray-800 p-5 rounded-xl flex items-center justify-between">
                      <div>
                        <span className="text-gray-300 font-bold text-base block">BTTS: 否 (No)</span>
                        <span className="text-xs text-gray-400">至少有一队被零封 (0球)</span>
                      </div>
                      <div className="text-right">
                        <span className="text-2xl font-black text-white">{(deriv.btts.no.prob * 100).toFixed(1)}%</span>
                        <span className="text-xs text-gray-400 block">公允赔率: {deriv.btts.no.fair_odds}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 4: Asian Handicap */}
              {activeTab === "HANDICAP" && deriv?.asian_handicap && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                    <ShieldCheck className="w-4 h-4 mr-1.5 text-blue-400" /> 亚洲让球盘 (Asian Handicap Lines)
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex justify-between items-center">
                      <div>
                        <span className="font-bold text-white block">主队 -0.5 球 (Home -0.5)</span>
                        <span className="text-[10px] text-gray-400">主队净胜1球及以上赢全盘</span>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-bold text-blue-400">{(deriv.asian_handicap.home_minus_0_5.prob * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-gray-400 block">公允: {deriv.asian_handicap.home_minus_0_5.fair_odds}</span>
                      </div>
                    </div>

                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex justify-between items-center">
                      <div>
                        <span className="font-bold text-white block">主队 +0.5 球 (Home +0.5)</span>
                        <span className="text-[10px] text-gray-400">主队胜或平局赢全盘 (相当于1X)</span>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-bold text-emerald-400">{(deriv.asian_handicap.home_plus_0_5.prob * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-gray-400 block">公允: {deriv.asian_handicap.home_plus_0_5.fair_odds}</span>
                      </div>
                    </div>

                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex justify-between items-center">
                      <div>
                        <span className="font-bold text-white block">主队 -1.5 球 (Home -1.5)</span>
                        <span className="text-[10px] text-gray-400">主队净胜2球及以上赢全盘</span>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-bold text-purple-400">{(deriv.asian_handicap.home_minus_1_5.prob * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-gray-400 block">公允: {deriv.asian_handicap.home_minus_1_5.fair_odds}</span>
                      </div>
                    </div>

                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex justify-between items-center">
                      <div>
                        <span className="font-bold text-white block">主队 +1.5 球 (Home +1.5)</span>
                        <span className="text-[10px] text-gray-400">主队净负1球以内均赢盘</span>
                      </div>
                      <div className="text-right">
                        <span className="text-base font-bold text-emerald-400">{(deriv.asian_handicap.home_plus_1_5.prob * 100).toFixed(1)}%</span>
                        <span className="text-[10px] text-gray-400 block">公允: {deriv.asian_handicap.home_plus_1_5.fair_odds}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 5: Double Chance & DNB */}
              {activeTab === "DC" && deriv?.double_chance && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4 font-mono text-xs">
                  <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                    <Layers className="w-4 h-4 mr-1.5 text-amber-400" /> 双胜彩 (Double Chance) 与 平局退款 (Draw No Bet)
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800">
                      <span className="text-gray-400 block">1X (主胜或平局)</span>
                      <span className="text-lg font-bold text-white mt-1 block">{(deriv.double_chance["1x"].prob * 100).toFixed(1)}%</span>
                      <span className="text-[10px] text-gray-500">公允赔率: {deriv.double_chance["1x"].fair_odds}</span>
                    </div>
                    <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800">
                      <span className="text-gray-400 block">X2 (平局或客胜)</span>
                      <span className="text-lg font-bold text-white mt-1 block">{(deriv.double_chance["x2"].prob * 100).toFixed(1)}%</span>
                      <span className="text-[10px] text-gray-500">公允赔率: {deriv.double_chance["x2"].fair_odds}</span>
                    </div>
                    <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800">
                      <span className="text-gray-400 block">12 (分胜负·无平局)</span>
                      <span className="text-lg font-bold text-white mt-1 block">{(deriv.double_chance["12"].prob * 100).toFixed(1)}%</span>
                      <span className="text-[10px] text-gray-500">公允赔率: {deriv.double_chance["12"].fair_odds}</span>
                    </div>
                  </div>

                  {deriv.draw_no_bet && (
                    <div className="pt-2">
                      <h5 className="text-xs font-bold text-gray-400 mb-2">平局退款 (DNB - Draw No Bet) 纯胜负概率：</h5>
                      <div className="grid grid-cols-2 gap-3">
                        <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800 flex justify-between items-center">
                          <span>DNB 主胜:</span>
                          <span className="font-bold text-blue-400">{(deriv.draw_no_bet.home.prob * 100).toFixed(1)}% (公允: {deriv.draw_no_bet.home.fair_odds})</span>
                        </div>
                        <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800 flex justify-between items-center">
                          <span>DNB 客胜:</span>
                          <span className="font-bold text-indigo-400">{(deriv.draw_no_bet.away.prob * 100).toFixed(1)}% (公允: {deriv.draw_no_bet.away.fair_odds})</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Tab 6: 6x6 Score Matrix */}
              {activeTab === "MATRIX" && data.prediction && data.prediction.score_matrix && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  {/* 6x6 Heatmap */}
                  <div className="lg:col-span-2 bg-[#090d16] rounded-xl border border-gray-800 p-5">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-bold text-white uppercase tracking-wider">
                        6×6 Goal Probability Matrix (Unconditional)
                      </h4>
                      <span className="text-[11px] font-mono text-gray-400">
                        Omitted Tail Mass: {(data.prediction.omitted_mass * 100).toFixed(2)}%
                      </span>
                    </div>

                    <p className="text-[11px] text-gray-500 mb-3">
                      Rows: Home Goals (0–5) | Columns: Away Goals (0–5)
                    </p>

                    <div className="overflow-x-auto">
                      <div className="inline-block min-w-full">
                        <table className="w-full text-center text-xs font-mono border-collapse">
                          <thead>
                            <tr>
                              <th className="p-1.5 text-gray-500 text-[10px]">H \ A</th>
                              {[0, 1, 2, 3, 4, 5].map((g) => (
                                <th key={g} className="p-1.5 text-gray-400 font-bold">
                                  {g}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {data.prediction.score_matrix.map((row: number[], hGoals: number) => (
                              <tr key={hGoals}>
                                <td className="p-1.5 text-gray-400 font-bold">{hGoals}</td>
                                {row.map((prob: number, aGoals: number) => {
                                  const opacity = Math.min(1, prob * 6);
                                  return (
                                    <td
                                      key={aGoals}
                                      style={{
                                        backgroundColor: `rgba(59, 130, 246, ${opacity * 0.4})`,
                                      }}
                                      className="p-1.5 border border-gray-800/60 rounded text-[11px] font-medium text-gray-200"
                                    >
                                      {(prob * 100).toFixed(1)}%
                                    </td>
                                  );
                                })}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>

                  {/* Top 3 Scores */}
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 flex flex-col justify-between">
                    <div>
                      <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">
                        Top 3 Likely Scores
                      </h4>
                      <div className="space-y-3 font-mono">
                        {data.prediction.top_scores.map((sc: any, idx: number) => (
                          <div
                            key={sc.score}
                            className="flex items-center justify-between p-3 bg-gray-900/60 border border-gray-800 rounded-lg"
                          >
                            <div className="flex items-center space-x-3">
                              <span className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-xs">
                                {idx + 1}
                              </span>
                              <span className="font-extrabold text-white text-base">{sc.score}</span>
                            </div>
                            <span className="text-emerald-400 font-bold text-sm">
                              {(sc.prob * 100).toFixed(2)}%
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="mt-4 pt-4 border-t border-gray-800 text-[11px] text-gray-500 font-mono">
                      <p>Training Cutoff: {new Date(data.prediction.training_cutoff).toUTCString()}</p>
                      <p>Decision Cutoff: {new Date(data.prediction.as_of).toUTCString()}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Tab 7: Custom Kelly Stake Calculator */}
              {activeTab === "STAKE" && data.comparison && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Calculator className="w-4 h-4 mr-1.5 text-emerald-400" /> 本场比赛凯利最优下注额计算器 (Custom Staking Calculator)
                    </h4>
                  </div>

                  <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex items-center space-x-4">
                    <label className="text-xs font-mono text-gray-300">请输入您的可用总本金 ($):</label>
                    <input
                      type="number"
                      value={calcBankroll}
                      onChange={(e) => setCalcBankroll(Math.max(10, Number(e.target.value)))}
                      className="w-32 px-3 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-sm font-bold focus:border-blue-500 focus:outline-none"
                    />
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
                    {data.comparison.outcomes.map((item: any) => {
                      const stakeAmt = item.half_kelly > 0 ? (calcBankroll * item.half_kelly).toFixed(2) : "0.00";
                      const expProf = item.ev > 0 ? (Number(stakeAmt) * item.ev).toFixed(2) : "0.00";
                      return (
                        <div
                          key={item.outcome}
                          className={`p-4 rounded-xl border ${
                            item.ev >= 0.05
                              ? "bg-emerald-950/20 border-emerald-500/40"
                              : "bg-[#0f1523] border-gray-800"
                          }`}
                        >
                          <div className="flex justify-between items-center mb-2">
                            <span className="font-bold text-white text-base">{item.outcome}</span>
                            <span className="text-gray-400">赔率: {item.odds}</span>
                          </div>
                          <div className="space-y-1.5 pt-2 border-t border-gray-800/80">
                            <div className="flex justify-between">
                              <span className="text-gray-400">半凯利建议比例:</span>
                              <span className="font-bold text-white">{(item.half_kelly * 100).toFixed(2)}%</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-400">建议下注金额:</span>
                              <span className="font-bold text-emerald-400 text-sm">${stakeAmt}</span>
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-400">单场数学期望利润:</span>
                              <span className="font-bold text-blue-400">+${expProf}</span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : null}
        </div>

        {/* Sticky Bottom Footer Bar */}
        <div className="px-5 sm:px-7 py-3 border-t border-gray-800 bg-[#090d16] flex items-center justify-between flex-shrink-0 text-xs text-gray-500 font-mono">
          <span>按 ESC 键或点击外部遮罩亦可快速关闭</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 font-semibold transition border border-gray-700 shadow-sm"
          >
            关闭窗口
          </button>
        </div>
      </div>
    </div>
  );
};
