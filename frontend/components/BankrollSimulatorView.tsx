"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Calculator, ShieldAlert, Sparkles, RefreshCw, TrendingUp, Percent, DollarSign, Activity } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface BankrollSimulatorViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
}

export const BankrollSimulatorView: React.FC<BankrollSimulatorViewProps> = () => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";

  const [bankroll, setBankroll] = useState<number>(10000);
  const [kellyFraction, setKellyFraction] = useState<number>(0.5);
  const [avgEv, setAvgEv] = useState<number>(0.065);
  const [avgOdds, setAvgOdds] = useState<number>(2.10);
  const [numBets, setNumBets] = useState<number>(100);

  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const runSimulation = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `/analytics/monte-carlo?bankroll=${bankroll}&kelly_fraction=${kellyFraction}&avg_ev=${avgEv}&avg_odds=${avgOdds}&num_bets=${numBets}&num_simulations=1000`;
      const res = await apiRequest<any>(url, { method: "POST" });
      setData(res);
    } catch (err: any) {
      setError(err?.message || (isEn ? "Failed to run Monte Carlo simulation." : "执行蒙特卡洛模拟失败。"));
    } finally {
      setLoading(false);
    }
  }, [bankroll, kellyFraction, avgEv, avgOdds, numBets, isEn]);

  useEffect(() => {
    runSimulation();
  }, [runSimulation]);

  const stats = data?.statistics;
  const trajectories = data?.sample_trajectories || [];

  const renderTrajectoriesSvg = () => {
    if (trajectories.length === 0) return null;
    const width = 800;
    const height = 240;
    const padding = 40;

    let allVals: number[] = [];
    trajectories.forEach((path: number[]) => {
      allVals.push(...path);
    });
    const minVal = Math.max(0, Math.min(...allVals) * 0.9);
    const maxVal = Math.max(...allVals) * 1.1;
    const range = maxVal - minVal || 1;

    const colors = [
      "#3b82f6", "#10b981", "#8b5cf6", "#ec4899",
      "#f59e0b", "#06b6d4", "#14b8a6", "#6366f1"
    ];

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
        {/* Horizontal grid */}
        {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
          const y = height - padding - pct * (height - 2 * padding);
          const val = maxVal - pct * range;
          return (
            <g key={i}>
              <line x1={padding} y1={y} x2={width - padding} y2={y} stroke="#1f293d" strokeDasharray="3,3" />
              <text x={padding - 5} y={y + 3} textAnchor="end" fill="#64748b" fontSize="10" fontFamily="monospace">
                ${Math.round(val).toLocaleString()}
              </text>
            </g>
          );
        })}

        {/* 10 Trajectories */}
        {trajectories.map((path: number[], pIdx: number) => {
          const color = colors[pIdx % colors.length];
          const points = path.map((val: number, stepIdx: number) => {
            const x = padding + (stepIdx / (path.length - 1)) * (width - 2 * padding);
            const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
            return `${x},${y}`;
          });

          return (
            <path
              key={pIdx}
              d={`M ${points.join(" L ")}`}
              fill="none"
              stroke={color}
              strokeWidth="1.8"
              strokeOpacity="0.85"
            />
          );
        })}
      </svg>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 sm:p-7 shadow-2xl relative">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20 mb-3">
              <Calculator className="w-3.5 h-3.5" />
              <span>{isEn ? "1,000-Path Monte Carlo Portfolio Engine" : "1,000 路径蒙特卡洛投资组合推演"}</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>💼 {t("simulator.title")}</span>
            </h2>
            <p className="text-xs sm:text-sm text-gray-400 mt-2 max-w-2xl leading-relaxed">
              {t("simulator.subtitle")}
            </p>
          </div>

          {/* Quick Config Form */}
          <div className="bg-[#090d16] border border-gray-800/80 rounded-xl p-4 flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Bankroll" : "本金规模"}
              </label>
              <input
                type="number"
                value={bankroll}
                onChange={(e) => setBankroll(Number(e.target.value))}
                className="w-24 px-2.5 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs font-bold"
              />
            </div>
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Kelly Fraction" : "凯利乘数"}
              </label>
              <select
                value={kellyFraction}
                onChange={(e) => setKellyFraction(Number(e.target.value))}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={0.25}>0.25x ({isEn ? "Conservative" : "超保守"})</option>
                <option value={0.5}>0.50x ({isEn ? "Half-Kelly" : "半凯利·机构标配"})</option>
                <option value={0.75}>0.75x ({isEn ? "Growth" : "积极"})</option>
                <option value={1.0}>1.00x ({isEn ? "Full-Kelly" : "全凯利·激进"})</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Sim Bets" : "模拟场次"}
              </label>
              <select
                value={numBets}
                onChange={(e) => setNumBets(Number(e.target.value))}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={50}>50 {isEn ? "Bets" : "场交易"}</option>
                <option value={100}>100 {isEn ? "Bets" : "场交易"}</option>
                <option value={200}>200 {isEn ? "Bets" : "场交易"}</option>
              </select>
            </div>
            <div className="self-end">
              <button
                onClick={runSimulation}
                disabled={loading}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold text-xs flex items-center transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                {isEn ? "Simulate" : "重新模拟"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.expectedMedian")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              ${stats.expected_bankroll_median.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">
              {isEn ? "Median Return" : "中位数收益"}: +{stats.median_growth_pct}%
            </span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.doubleProb")}</span>
            <span className="text-xl sm:text-2xl font-black text-blue-400 mt-1 block">
              {stats.probability_doubling_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Reaching" : "达到"} ${ (bankroll * 2).toLocaleString() }</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.bestCase")}</span>
            <span className="text-xl sm:text-2xl font-black text-purple-400 mt-1 block">
              ${stats.best_case_p95.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Upside Limit" : "顺风上限区间"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.worstCase")}</span>
            <span className="text-xl sm:text-2xl font-black text-amber-400 mt-1 block">
              ${stats.worst_case_p5.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Extreme Drawdown" : "极端连黑抗压底线"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.ruinRisk")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              {stats.risk_of_ruin_pct}%
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">{isEn ? "Safe Half-Kelly Buffer" : "严格半凯利免爆仓"}</span>
          </div>
        </div>
      )}

      {/* Trajectories Visualizer */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-400" />
              {t("simulator.paths")}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">
              {isEn ? `X: Bet Sequence (0~${numBets}) · Y: Portfolio Equity ($)` : `横轴: 下注场次 (0~${numBets}) · 纵轴: 本金规模 ($) · 包含多条随机推演路径`}
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
            {isEn ? "Kelly Multiplier" : "凯利分数"}: {kellyFraction}x
          </span>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-gray-400 font-mono">{isEn ? "Running 1,000-path Monte Carlo matrix..." : "运行 1,000 次路径蒙特卡洛矩阵推演..."}</p>
          </div>
        ) : (
          <div className="py-2">
            {renderTrajectoriesSvg()}
          </div>
        )}
      </div>
    </div>
  );
};
