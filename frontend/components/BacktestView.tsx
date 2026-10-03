"use client";

import React, { useState, useEffect, useCallback } from "react";
import { TrendingUp, ShieldCheck, Award, BarChart3, RefreshCw, Layers, CheckCircle2, Target, Calendar } from "lucide-react";
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
  const [dataset, setDataset] = useState<string>("HISTORICAL_10Y");
  const [years, setYears] = useState<number>(10);
  const [bankroll, setBankroll] = useState<number>(10000);
  const [strategy, setStrategy] = useState<string>("HALF_KELLY");
  const [minEv, setMinEv] = useState<number>(0.04);
  const [league, setLeague] = useState<string>("ALL");

  const runBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let url = `/analytics/backtest?initial_bankroll=${bankroll}&staking_strategy=${strategy}&min_ev=${minEv}&dataset=${dataset}&years=${years}`;
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
  }, [bankroll, strategy, minEv, league, dataset, years, isEn]);

  useEffect(() => {
    if (!isAnalyst) {
      setLoading(false);
      return;
    }
    runBacktest();
  }, [runBacktest, isAnalyst]);

  const summary = data?.summary;
  const equityCurve = data?.equity_curve || [];
  const recentBets = data?.recent_bets || [];

  if (!isAnalyst) {
    return (
      <div className="border-y border-gray-800 py-16 text-center bg-[#0d121f] rounded-2xl p-8 border">
        <ShieldCheck className="w-10 h-10 text-blue-400 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-white">{isEn ? "10+ Years Historical Backtest Terminal" : "10+ 年真实历史回测终端"}</h2>
        <p className="text-sm text-gray-400 mt-2 max-w-xl mx-auto">
          {isEn
            ? "An active Analyst Pass is required to execute walk-forward backtests on 11,329 real English Premier League & Championship fixtures across 2014-2026."
            : "运行基于 2014-2026 年英超与英冠 11,329 场真实赔率与赛果的历史步进回测需要 Analyst 权限。"}
        </p>
        <button
          onClick={onOpenPricing}
          className="mt-5 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/25 transition"
        >
          {isEn ? "Upgrade to Analyst Pass ($29)" : "开通 Analyst 专属通行证 ($29)"}
        </button>
      </div>
    );
  }

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
            <stop offset="0%" stopColor="#10b981" stopOpacity="0.32" />
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
              <text x={padding - 8} y={y + 3} textAnchor="end" fill="#64748b" fontSize="10" fontFamily="monospace">
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
      {/* Header & Controls Panel */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 sm:p-7 shadow-2xl relative">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-3">
              <Award className="w-3.5 h-3.5" />
              <span>
                {dataset === "HISTORICAL_10Y"
                  ? (isEn ? "10+ Years Real Odds & Score Verification (11,329 Matches)" : "英格兰 10+ 年真实历史赔率与赛果回测（11,329 场）")
                  : (isEn ? "Database Active Snapshot" : "数据库快照运行")}
              </span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight flex items-center gap-3">
              <span>📈 {t("backtest.title")}</span>
            </h2>
            <p className="text-xs sm:text-sm text-gray-400 mt-2 max-w-2xl leading-relaxed">
              {isEn
                ? "Simulate walking-forward Dixon-Coles and Shin de-vigged value betting across 10+ years of English football. Track real ROI, drawdown curves, and closing line value (CLV)."
                : "复盘基于 Dixon-Coles 与 Shin 去水模型的 +EV 价值投资策略在英格兰近 10+ 年比赛中的表现，验证真实收益率、最大回撤与收盘赔率优势（CLV）。"}
            </p>
          </div>

          {/* Quick Stats Pill */}
          {summary && (
            <div className="bg-[#0b0f1a] border border-gray-800 rounded-xl p-3.5 text-right font-mono flex items-center gap-4 self-start lg:self-auto">
              <div>
                <span className="text-[10px] text-gray-400 block uppercase tracking-wider">{isEn ? "Historical ROI" : "历史投资回报率"}</span>
                <span className="text-xl font-black text-emerald-400">
                  {summary.roi_pct >= 0 ? "+" : ""}{summary.roi_pct}%
                </span>
              </div>
              <div className="border-l border-gray-800 pl-4">
                <span className="text-[10px] text-gray-400 block uppercase tracking-wider">{isEn ? "Beat CLV Rate" : "战胜终盘率 (CLV)"}</span>
                <span className="text-xl font-black text-blue-400">
                  {summary.beat_clv_rate_pct != null ? `${summary.beat_clv_rate_pct}%` : "—"}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Controls Grid */}
        <div className="mt-6 pt-5 border-t border-gray-800/80 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
          {/* Dataset Source */}
          <div>
            <label className="text-[11px] font-mono text-gray-400 block mb-1">
              {isEn ? "Data Source" : "数据来源"}
            </label>
            <select
              value={dataset}
              onChange={(e) => setDataset(e.target.value)}
              className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs"
            >
              <option value="HISTORICAL_10Y">{isEn ? "10Y Real England (11k)" : "10年真实英格兰(1.1万场)"}</option>
              <option value="DATABASE">{isEn ? "DB Snapshots" : "数据库快照"}</option>
            </select>
          </div>

          {/* Timeframe */}
          {dataset === "HISTORICAL_10Y" && (
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Timeframe" : "回测周期"}
              </label>
              <select
                value={years}
                onChange={(e) => setYears(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={10}>{isEn ? "All 10+ Years (2014-26)" : "完整 10+ 年 (2014-2026)"}</option>
                <option value={5}>{isEn ? "Recent 5 Years (2022-26)" : "最近 5 年 (2022-2026)"}</option>
                <option value={3}>{isEn ? "Recent 3 Years (2024-26)" : "最近 3 年 (2024-2026)"}</option>
              </select>
            </div>
          )}

          {/* League Filter */}
          <div>
            <label className="text-[11px] font-mono text-gray-400 block mb-1">
              {isEn ? "League" : "联赛范围"}
            </label>
            <select
              value={league}
              onChange={(e) => setLeague(e.target.value)}
              className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs"
            >
              <option value="ALL">{isEn ? "All (EPL + Champ)" : "英超 + 英冠全部"}</option>
              <option value="EPL">{isEn ? "Premier League (EPL)" : "仅英超 (Premier League)"}</option>
              <option value="CHAMPIONSHIP">{isEn ? "Championship (EFL)" : "仅英冠 (Championship)"}</option>
            </select>
          </div>

          {/* Initial Capital */}
          <div>
            <label className="text-[11px] font-mono text-gray-400 block mb-1">
              {t("backtest.initialCapital")}
            </label>
            <input
              type="number"
              value={bankroll}
              onChange={(e) => setBankroll(Number(e.target.value))}
              className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs font-bold"
            />
          </div>

          {/* Staking Strategy */}
          <div>
            <label className="text-[11px] font-mono text-gray-400 block mb-1">
              {isEn ? "Staking" : "仓位策略"}
            </label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs"
            >
              <option value="HALF_KELLY">{isEn ? "Half-Kelly (0.5x)" : "半凯利 (Half-Kelly)"}</option>
              <option value="QUARTER_KELLY">{isEn ? "Quarter-Kelly (0.25x)" : "四分之一凯利 (保守)"}</option>
              <option value="FIXED_1_PCT">{isEn ? "Fixed 1%" : "固定 1%"}</option>
              <option value="FLAT_UNIT">{isEn ? "Flat Unit" : "平注 (Flat)"}</option>
            </select>
          </div>

          {/* Min EV */}
          <div>
            <label className="text-[11px] font-mono text-gray-400 block mb-1">
              {isEn ? "Min EV Threshold" : "最低 EV 阈值"}
            </label>
            <div className="flex gap-2">
              <select
                value={minEv}
                onChange={(e) => setMinEv(Number(e.target.value))}
                className="w-full px-2.5 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-xs"
              >
                <option value={0.03}>EV ≥ 3%</option>
                <option value={0.04}>EV ≥ 4%</option>
                <option value={0.05}>EV ≥ 5%</option>
                <option value={0.08}>EV ≥ 8%</option>
              </select>
              <button
                onClick={runBacktest}
                disabled={loading}
                className="px-3.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-bold text-xs flex items-center transition flex-shrink-0"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {/* Net Profit */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.profit")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              {summary.net_profit >= 0 ? "+" : ""}${summary.net_profit.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">ROI: {summary.roi_pct >= 0 ? "+" : ""}{summary.roi_pct}%</span>
          </div>

          {/* Beat CLV Rate */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.beatClv")}</span>
            <span className="text-xl sm:text-2xl font-black text-blue-400 mt-1 block">
              {summary.beat_clv_rate_pct == null ? "—" : `${summary.beat_clv_rate_pct}%`}
            </span>
            <span className="text-[10px] font-mono text-emerald-400">
              {summary.avg_clv_edge_pct ? `+${summary.avg_clv_edge_pct}% avg edge` : (isEn ? "Pinnacle/B365 Close" : "战胜终盘赔率")}
            </span>
          </div>

          {/* Sharpe */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.sharpe")}</span>
            <span className="text-xl sm:text-2xl font-black text-purple-400 mt-1 block">
              {summary.sharpe_ratio ?? "—"}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Annualized Risk-Adj" : "年化风险收益比"}</span>
          </div>

          {/* Max DD */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.maxDd")}</span>
            <span className="text-xl sm:text-2xl font-black text-rose-400 mt-1 block">
              -{summary.max_drawdown_pct}%
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Peak-to-Trough" : "峰谷最大回撤"}</span>
          </div>

          {/* Trades & Win Rate */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("backtest.totalTrades")}</span>
            <span className="text-xl sm:text-2xl font-black text-white mt-1 block">
              {summary.total_bets}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Win Rate" : "命中率"}: {summary.win_rate_pct}%</span>
          </div>

          {/* Brier Gain */}
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{isEn ? "Total Staked" : "总周转投注量"}</span>
            <span className="text-xl sm:text-2xl font-black text-amber-400 mt-1 block">
              ${summary.total_staked.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Turnover Capital" : "本金周转规模"}</span>
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
            {isEn ? "Net PnL" : "净盈亏"}: {summary?.net_profit >= 0 ? "+" : ""}${summary?.net_profit.toLocaleString()}
          </span>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            <p className="text-xs text-gray-400 font-mono">{isEn ? "Simulating walk-forward historical bets..." : "正在进行历史步进式策略回测..."}</p>
          </div>
        ) : (
          <div className="py-2" role="status">
            {renderEquitySvg() || (
              <p className="py-12 text-center text-sm text-gray-400">
                {isEn ? "No qualifying trades to plot." : "没有符合筛选条件的投注可绘制。"}
              </p>
            )}
          </div>
        )}
      </div>

      {/* Recent Sample Bets Log with CLV Badges */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl overflow-hidden shadow-xl">
        <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-blue-400" />
            {t("backtest.recentTrades")}
          </h3>
          <span className="text-xs font-mono text-gray-400">
            {isEn ? `Auditing recent sample of ${summary?.total_bets ?? 0} matches` : `展示 ${summary?.total_bets ?? 0} 笔历史样本的最近对账记录`}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-gray-800/80 bg-[#0a0e1a] text-gray-400 text-[11px]">
                <th className="py-2.5 px-4">{isEn ? "ID" : "单号"}</th>
                <th className="py-2.5 px-4">{isEn ? "Date / Season" : "日期 / 赛季"}</th>
                <th className="py-2.5 px-4">{isEn ? "League & Fixture" : "赛事对阵"}</th>
                <th className="py-2.5 px-4">{isEn ? "Selection" : "方向"}</th>
                <th className="py-2.5 px-4">{isEn ? "Odds" : "买入赔率"}</th>
                <th className="py-2.5 px-4">{isEn ? "Closing (CLV)" : "终盘赔率 (CLV)"}</th>
                <th className="py-2.5 px-4">{isEn ? "EV (%)" : "期望 EV"}</th>
                <th className="py-2.5 px-4">{isEn ? "Stake" : "下注额"}</th>
                <th className="py-2.5 px-4">{isEn ? "PnL" : "赛果盈亏"}</th>
                <th className="py-2.5 px-4">{isEn ? "Balance" : "结余本金"}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {recentBets.length === 0 && (
                <tr>
                  <td colSpan={10} className="py-8 px-4 text-center text-sm text-gray-500">
                    {isEn ? "No bets meet the selected filters." : "没有投注达到当前筛选条件。"}
                  </td>
                </tr>
              )}
              {recentBets.map((b: any) => (
                <tr key={b.bet_id} className="hover:bg-gray-800/30">
                  <td className="py-2.5 px-4 text-gray-400">{b.bet_id}</td>
                  <td className="py-2.5 px-4 text-gray-300">
                    <div>{b.date}</div>
                    {b.season && <span className="text-[10px] text-gray-400">{b.season}</span>}
                  </td>
                  <td className="py-2.5 px-4">
                    <span className="font-bold text-white block">{b.match}</span>
                    <span className="text-[10px] text-blue-400">{b.league}</span>
                  </td>
                  <td className="py-2.5 px-4 font-bold text-white">
                    <span className="px-2 py-0.5 rounded bg-gray-800 text-gray-200">
                      {b.selection}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-white font-bold">{b.odds}</td>
                  <td className="py-2.5 px-4">
                    {b.beat_clv ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] bg-emerald-500/15 text-emerald-400 font-bold border border-emerald-500/30">
                        {b.closing_odds} ({b.clv_edge_pct ? `+${b.clv_edge_pct}%` : "✓ CLV"})
                      </span>
                    ) : (
                      <span className="text-gray-400 font-mono">
                        {b.closing_odds ?? "—"}
                      </span>
                    )}
                  </td>
                  <td className="py-2.5 px-4 text-emerald-400 font-bold">{b.ev_pct >= 0 ? "+" : ""}{b.ev_pct}%</td>
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
