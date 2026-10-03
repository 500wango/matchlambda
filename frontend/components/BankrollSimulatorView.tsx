"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Calculator, ShieldAlert, Sparkles, RefreshCw, TrendingUp, Percent, DollarSign, Activity } from "lucide-react";
import { apiRequest } from "@/lib/api";

interface BankrollSimulatorViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
}

export const BankrollSimulatorView: React.FC<BankrollSimulatorViewProps> = () => {
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
      setError(err?.message || "Failed to run Monte Carlo simulation.");
    } finally {
      setLoading(false);
    }
  }, [bankroll, kellyFraction, avgEv, avgOdds, numBets]);

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
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-60 overflow-visible">
        {/* Gridlines */}
        {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
          const y = padding + pct * (height - 2 * padding);
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
        {/* Paths */}
        {trajectories.map((path: number[], pIdx: number) => {
          const points = path.map((val: number, stepIdx: number) => {
            const x = padding + (stepIdx / (path.length - 1)) * (width - 2 * padding);
            const y = height - padding - ((val - minVal) / range) * (height - 2 * padding);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
          });
          return (
            <path
              key={pIdx}
              d={`M ${points.join(" L ")}`}
              fill="none"
              stroke={colors[pIdx % colors.length]}
              strokeWidth={pIdx === 0 ? "2.5" : "1.5"}
              strokeOpacity={pIdx === 0 ? 1 : 0.65}
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
              <span>1,000-Path Monte Carlo Portfolio Engine</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>💼 蒙特卡洛资金曲线与破产风险模拟器</span>
            </h2>
            <p className="text-xs sm:text-sm text-gray-400 mt-2 max-w-2xl leading-relaxed">
              基于凯利公式（Kelly Criterion）进行 1,000 次独立全景路径推演。量化预测在不同下注纪律下本金翻倍的概率、极值压力测试（5% 最坏情形）以及防破产（Ruin Risk）边界。
            </p>
          </div>

          {/* Quick Config Form */}
          <div className="bg-[#090d16] border border-gray-800/80 rounded-xl p-4 flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">本金规模</label>
              <input
                type="number"
                value={bankroll}
                onChange={(e) => setBankroll(Number(e.target.value))}
                className="w-24 px-2.5 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs font-bold"
              />
            </div>
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">凯利乘数</label>
              <select
                value={kellyFraction}
                onChange={(e) => setKellyFraction(Number(e.target.value))}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={0.25}>0.25x (超保守)</option>
                <option value={0.5}>0.50x (半凯利·机构标配)</option>
                <option value={0.75}>0.75x (积极)</option>
                <option value={1.0}>1.00x (全凯利·激进)</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">模拟场次</label>
              <select
                value={numBets}
                onChange={(e) => setNumBets(Number(e.target.value))}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={50}>50 场交易</option>
                <option value={100}>100 场交易</option>
                <option value={200}>200 场交易</option>
              </select>
            </div>
            <div className="self-end">
              <button
                onClick={runSimulation}
                disabled={loading}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold text-xs flex items-center transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                重新模拟
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">中位数预期终值 (P50)</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              ${stats.expected_bankroll_median.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">
              中位数收益: +{stats.median_growth_pct}%
            </span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">翻倍概率 (P ≥ 2x)</span>
            <span className="text-xl sm:text-2xl font-black text-blue-400 mt-1 block">
              {stats.probability_doubling_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">达到 ${ (bankroll * 2).toLocaleString() }</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">95% 乐观边界 (P95)</span>
            <span className="text-xl sm:text-2xl font-black text-purple-400 mt-1 block">
              ${stats.best_case_p95.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-gray-400">顺风上限区间</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">5% 极端压力底线 (P5)</span>
            <span className="text-xl sm:text-2xl font-black text-amber-400 mt-1 block">
              ${stats.worst_case_p5.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-gray-400">极端连黑抗压底线</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">破产风险 (Ruin Risk)</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              {stats.risk_of_ruin_pct}%
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">严格半凯利免爆仓</span>
          </div>
        </div>
      )}

      {/* Trajectories Visualizer */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Activity className="w-4 h-4 text-purple-400" />
              1,000 次模拟样本走势图 (Random Walk Sample Paths)
            </h3>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">
              横轴: 下注场次 (0~{numBets}) · 纵轴: 本金规模 ($) · 包含多条随机推演路径
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-purple-500/10 text-purple-400 border border-purple-500/20 font-bold">
            凯利分数: {kellyFraction}x
          </span>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-gray-400 font-mono">运行 1,000 次路径蒙特卡洛矩阵推演...</p>
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
