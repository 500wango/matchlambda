"use client";

import React, { useState, useEffect, useCallback } from "react";
import { LineChart, TrendingUp, ShieldCheck, Award, AlertCircle, BarChart3, RefreshCw, CheckCircle2, DollarSign } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface BacktestViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
}

export const BacktestView: React.FC<BacktestViewProps> = ({ isAnalyst, onOpenPricing }) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";

  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Settings
  const [bankroll, setBankroll] = useState<number>(10000);
  const [strategy, setStrategy] = useState<string>("HALF_KELLY");
  const [minEv, setMinEv] = useState<number>(0.04);
  const [league, setLeague] = useState<string>("ALL");

  const runBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `/analytics/backtest?initial_bankroll=${bankroll}&staking_strategy=${strategy}&min_ev=${minEv}`;
      if (league && league !== "ALL") {
        url += `&league_id=${league}`;
      }
      const res = await apiRequest<any>(url);
      setData(res);
    } catch (err: any) {
      setError(err?.message || (isEn ? "Failed to execute backtest simulation." : "执行量化回测失败。"));
    } finally {
      setLoading(false);
    }
  }, [bankroll, strategy, minEv, league, isEn]);

  useEffect(() => {
    runBacktest();
  }, [runBacktest]);

  const summary = data?.summary;
  const equityCurve = data?.equity_curve || [];
  const recentBets = data?.recent_bets || [];

  // Generate SVG path for equity curve
  const renderEquitySvg = () => {
    if (equityCurve.length < 2) return null;

    const width = 800;
    const height = 260;
    const padding = 50;

    const bankrolls = equityCurve.map((p: any) => p.bankroll);
    const minVal = Math.min(...bankrolls);
    const maxVal = Math.max(...bankrolls);
    const range = maxVal - minVal || 1;

    const points = equityCurve.map((p: any, idx: number) => {
      const x = padding + (idx / (equityCurve.length - 1)) * (width - 2 * padding);
      const y = height - padding - ((p.bankroll - minVal) / range) * (height - 2 * padding);
      return `${x},${y}`;
    });

    const pathD = `M ${points.join(" L ")}`;
    const areaD = `M ${points[0]} L ${points.join(" L ")} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`;

    return (
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
        <defs>
          <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.28" />
            <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
          </linearGradient>
        </defs>
        {/* Horizontal gridlines */}
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
        {/* Area & Line */}
        <path d={areaD} fill="url(#equityGrad)" />
        <path d={pathD} fill="none" stroke="#10b981" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 sm:p-7 shadow-2xl relative">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
              <Award className="w-3.5 h-3.5" />
              <span>{isEn ? "Multi-Season Historical Validation & CLV Benchmark" : "多赛季实盘检验与收盘线 (CLV) 基准"}</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>📈 {t("backtest.title")}</span>
            </h2>
            <p className="text-xs sm:text-sm text-gray-400 mt-2 max-w-2xl leading-relaxed">
              {t("backtest.subtitle")}
            </p>
          </div>

          {/* Controls */}
          <div className="bg-[#090d16] border border-gray-800/80 rounded-xl p-4 flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {t("backtest.initialCapital")}
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
                {isEn ? "Staking" : "仓位管理"}
              </label>
              <select
                value={strategy}
                onChange={(e) => setStrategy(e.target.value)}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value="HALF_KELLY">{isEn ? "Half-Kelly (0.5x)" : "半凯利 (Half-Kelly)"}</option>
                <option value="QUARTER_KELLY">{isEn ? "Quarter-Kelly (0.25x)" : "四分之一凯利 (保守)"}</option>
                <option value="FIXED_1_PCT">{isEn ? "Fixed 1%" : "固定 1%"}</option>
                <option value="FLAT_UNIT">{isEn ? "Flat Unit" : "平注 (Flat)"}</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Min EV" : "最低 EV"}
              </label>
              <select
                value={minEv}
                onChange={(e) => setMinEv(Number(e.target.value))}
                className="px-2 py-1.5 bg-[#0f1523] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={0.02}>EV ≥ 2%</option>
                <option value={0.04}>EV ≥ 4%</option>
                <option value={0.08}>EV ≥ 8%</option>
              </select>
            </div>
            <div className="self-end">
              <button
                onClick={runBacktest}
                disabled={loading}
                className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold text-xs flex items-center transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                {isEn ? "Recalculate" : "重新运算"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.profit")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              +${summary.net_profit.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">ROI: +{summary.roi_pct}%</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.beatClv")}</span>
            <span className="text-xl sm:text-2xl font-black text-blue-400 mt-1 block">
              {summary.beat_clv_rate_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Beating Pinnacle CLV" : "击败平博终盘"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.sharpe")}</span>
            <span className="text-xl sm:text-2xl font-black text-purple-400 mt-1 block">
              {summary.sharpe_ratio}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Annualized Risk-Adj" : "年化风险调整"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.maxDd")}</span>
            <span className="text-xl sm:text-2xl font-black text-rose-400 mt-1 block">
              -{summary.max_drawdown_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Peak-to-Trough" : "峰谷最大下撤"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.totalTrades")}</span>
            <span className="text-xl sm:text-2xl font-black text-white mt-1 block">
              {summary.total_bets}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Win Rate" : "胜率"}: {summary.win_rate_pct}%</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{isEn ? "Brier Gain" : "Brier 评分改善"}</span>
            <span className="text-xl sm:text-2xl font-black text-amber-400 mt-1 block">
              +{summary.brier_improvement_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Edge vs Market" : "校准超越市场"}</span>
          </div>
        </div>
      )}

      {/* Interactive Equity Curve Chart */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              {t("backtest.equityCurve")}
            </h3>
            <p className="text-xs text-gray-400 mt-0.5 font-mono">
              {isEn ? "Initial Capital" : "初始本金"}: ${bankroll.toLocaleString()} → {isEn ? "Final" : "终值"}: ${summary?.final_bankroll.toLocaleString()}
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
            {isEn ? "Net PnL" : "净胜"}: +${summary?.net_profit.toLocaleString()}
          </span>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-gray-400 font-mono">{isEn ? "Computing multi-season equity curve..." : "计算多赛季净值曲线..."}</p>
          </div>
        ) : (
          <div className="py-2">
            {renderEquitySvg()}
          </div>
        )}
      </div>

      {/* Recent Sample Bets Log */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            {t("backtest.recentTrades")}
          </h3>
          <span className="text-xs font-mono text-gray-400">{isEn ? "Showing recent 20 audits" : "展示最近 20 笔决策"}</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-gray-800/80 bg-[#0a0e1a] text-gray-400 text-[11px]">
                <th className="py-2.5 px-4">{isEn ? "ID" : "单号"}</th>
                <th className="py-2.5 px-4">{isEn ? "Date" : "日期"}</th>
                <th className="py-2.5 px-4">{isEn ? "League" : "联赛"}</th>
                <th className="py-2.5 px-4">{isEn ? "Selection" : "方向"}</th>
                <th className="py-2.5 px-4">{isEn ? "Odds" : "下单赔率"}</th>
                <th className="py-2.5 px-4">{isEn ? "CLV" : "终盘赔率 (CLV)"}</th>
                <th className="py-2.5 px-4">{isEn ? "EV (%)" : "期望 EV"}</th>
                <th className="py-2.5 px-4">{isEn ? "Stake" : "下注额"}</th>
                <th className="py-2.5 px-4">{isEn ? "PnL" : "赛果盈亏"}</th>
                <th className="py-2.5 px-4">{isEn ? "Balance" : "结余本金"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {recentBets.map((b: any) => (
                <tr key={b.bet_id} className="hover:bg-gray-800/30">
                  <td className="py-2.5 px-4 text-gray-400">{b.bet_id}</td>
                  <td className="py-2.5 px-4 text-gray-300">{b.date}</td>
                  <td className="py-2.5 px-4 text-blue-400 font-bold">{b.league}</td>
                  <td className="py-2.5 px-4 font-bold text-white">{b.selection}</td>
                  <td className="py-2.5 px-4 text-white font-bold">{b.odds}</td>
                  <td className="py-2.5 px-4">
                    <span className={b.beat_clv ? "text-emerald-400 font-bold" : "text-gray-400"}>
                      {b.closing_odds} {b.beat_clv ? "✓" : ""}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-emerald-400 font-bold">+{b.ev_pct}%</td>
                  <td className="py-2.5 px-4 text-white">${b.stake}</td>
                  <td className="py-2.5 px-4 font-bold">
                    <span className={b.won ? "text-emerald-400" : "text-rose-400"}>
                      {b.won ? `+$${b.pnl}` : `-$${b.stake}`}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-gray-200 font-bold">${b.bankroll}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
