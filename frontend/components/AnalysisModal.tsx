"use client";

import React, { useState, useEffect } from "react";
import { X, Clock, AlertTriangle, Activity, Database, CheckCircle, Flame } from "lucide-react";
import { apiRequest } from "@/lib/api";

interface AnalysisModalProps {
  matchId: string | null;
  fixture?: any;
  onClose: () => void;
}

export const AnalysisModal: React.FC<AnalysisModalProps> = ({ matchId, fixture, onClose }) => {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
                  {fixture ? `${fixture.home_team.name} vs ${fixture.away_team.name}` : "Dixon–Coles 深度模型分析"}
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
            aria-label="关闭窗口"
          >
            <span>关闭</span>
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-6">
          {loading ? (
            <div className="py-24 text-center">
              <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-xs text-gray-400 font-mono">Computing Dixon–Coles probabilities...</p>
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
              <div className="border-b border-gray-800 pb-5">
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
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 text-xs font-mono">
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Home Rate (λ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.lambda_home.toFixed(3)}</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Away Rate (μ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.mu_away.toFixed(3)}</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Low-score Rho (ρ)</span>
                      <span className="font-bold text-white text-sm">{data.prediction.rho.toFixed(4)}</span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">Model Version</span>
                      <span className="font-bold text-blue-400 text-sm">{data.prediction.model_version}</span>
                    </div>
                  </div>
                )}
              </div>

              {/* 1X2 Probabilities & Value Comparison */}
              {data.comparison && data.comparison.outcomes && (
                <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5">
                  <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Flame className="w-4 h-4 mr-1.5 text-blue-400" /> 1X2 Probability & Value Comparison
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
                              <td className="py-2.5 font-bold text-white">{item.outcome}</td>
                              <td className="py-2.5 text-blue-400 font-semibold">
                                {(item.model_prob * 100).toFixed(2)}%
                              </td>
                              <td className="py-2.5 text-gray-400">
                                {(item.market_prob * 100).toFixed(2)}%
                              </td>
                              <td className="py-2.5 text-white font-bold">{item.odds.toFixed(2)}</td>
                              <td className="py-2.5">
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
                              <td className="py-2.5 text-gray-300">
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

              {/* Score Distribution Matrix 6x6 & Top Scores */}
              {data.prediction && data.prediction.score_matrix && (
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
