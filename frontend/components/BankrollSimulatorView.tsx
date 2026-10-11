"use client";

import React, { useState, useEffect, useRef } from "react";
import { Calculator, RefreshCw, Activity, ShieldCheck } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useDebounced } from "@/lib/useDebounced";

interface BankrollSimulatorViewProps {
  isAnalyst?: boolean;
  onOpenPricing?: () => void;
}

function finiteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function fmtMoney(value: unknown): string {
  const n = finiteNumber(value);
  return n == null ? "—" : `$${n.toLocaleString()}`;
}

function fmtPct(value: unknown, withPlus = false): string {
  const n = finiteNumber(value);
  if (n == null) return "—";
  if (withPlus && n > 0) return `+${n}%`;
  return `${n}%`;
}

function pathExtremes(trajectories: unknown[]): { min: number; max: number } | null {
  let min = Infinity;
  let max = -Infinity;
  for (const path of trajectories) {
    if (!Array.isArray(path)) continue;
    for (const raw of path) {
      const n = finiteNumber(raw);
      if (n == null) continue;
      if (n < min) min = n;
      if (n > max) max = n;
    }
  }
  if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
  return { min, max };
}

export const BankrollSimulatorView: React.FC<BankrollSimulatorViewProps> = ({
  isAnalyst = false,
  onOpenPricing = () => {},
}) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  // Language only affects copy, not the simulation request; a ref keeps a
  // language switch from re-firing the Monte Carlo run.
  const isEnRef = useRef(isEn);
  isEnRef.current = isEn;

  const [bankrollInput, setBankrollInput] = useState("10000");
  const [kellyFraction, setKellyFraction] = useState<number>(0.5);
  const [avgEv] = useState<number>(0.065);
  const [avgOdds] = useState<number>(2.1);
  const [numBets, setNumBets] = useState<number>(100);
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [monthlyPrice, setMonthlyPrice] = useState<number | null>(null);

  const debouncedBankrollInput = useDebounced(bankrollInput, 500);
  const debouncedKelly = useDebounced(kellyFraction, 500);
  const debouncedAvgEv = useDebounced(avgEv, 500);
  const debouncedAvgOdds = useDebounced(avgOdds, 500);
  const debouncedNumBets = useDebounced(numBets, 500);
  const bankroll = Number(debouncedBankrollInput);

  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAnalyst) return;
    let cancelled = false;
    apiRequest<{ monthly_price_usd: number }>("/payments/pricing")
      .then((res) => {
        if (cancelled) return;
        const price = Number(res?.monthly_price_usd);
        setMonthlyPrice(Number.isFinite(price) ? price : Number.NaN);
      })
      .catch(() => {
        // Locked screen stays without a price until the public quote loads.
      });
    return () => {
      cancelled = true;
    };
  }, [isAnalyst]);

  useEffect(() => {
    if (!isAnalyst) {
      setLoading(false);
      return;
    }
    if (!Number.isFinite(bankroll) || bankroll < 100) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      bankroll: String(bankroll),
      kelly_fraction: String(debouncedKelly),
      avg_ev: String(debouncedAvgEv),
      avg_odds: String(debouncedAvgOdds),
      num_bets: String(debouncedNumBets),
      num_simulations: "1000",
    });
    apiRequest<any>(`/analytics/monte-carlo?${params.toString()}`, {
      method: "POST",
      signal: controller.signal,
    })
      .then((res) => {
        if (!active) return;
        setData(res);
        setError(null);
      })
      .catch((err: any) => {
        if (!active || controller.signal.aborted || err?.code === "ABORTED") return;
        setError(err?.message || (isEnRef.current ? "Failed to run Monte Carlo simulation." : "执行蒙特卡洛模拟失败。"));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort(new Error("Bankroll simulator unmounted"));
    };
  }, [
    isAnalyst,
    bankroll,
    debouncedKelly,
    debouncedAvgEv,
    debouncedAvgOdds,
    debouncedNumBets,
    refreshNonce,
  ]);

  const stats = data?.statistics;
  const trajectories = data?.sample_trajectories || [];
  const doubleTarget = finiteNumber(bankroll);

  const renderTrajectoriesSvg = () => {
    if (trajectories.length === 0) return null;
    const width = 800;
    const height = 240;
    const padding = 40;
    const bounds = pathExtremes(trajectories);
    if (!bounds) return null;

    const minVal = Math.max(0, bounds.min * 0.9);
    const maxVal = bounds.max * 1.1;
    const range = maxVal - minVal || 1;

    const colors = [
      "#3b82f6", "#10b981", "#8b5cf6", "#ec4899",
      "#f59e0b", "#06b6d4", "#14b8a6", "#6366f1",
    ];

    return (
      <svg
        role="img"
        aria-label={t("simulator.paths")}
        viewBox={`0 0 ${width} ${height}`}
        className="w-full h-auto overflow-visible"
      >
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

        {trajectories.map((path: number[], pIdx: number) => {
          if (!Array.isArray(path) || path.length === 0) return null;
          const color = colors[pIdx % colors.length];
          const steps = Math.max(path.length - 1, 1);
          const points = path.map((val: number, stepIdx: number) => {
            const n = finiteNumber(val);
            const x = padding + (stepIdx / steps) * (width - 2 * padding);
            const y =
              n == null
                ? height - padding
                : height - padding - ((n - minVal) / range) * (height - 2 * padding);
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

  if (!isAnalyst) {
    return (
      <div className="border-y border-gray-800 py-16 text-center bg-[#0d121f] rounded-2xl p-8 border">
        <ShieldCheck className="w-10 h-10 text-blue-400 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-white">{t("simulator.title")}</h2>
        <p className="text-sm text-gray-400 mt-2 max-w-xl mx-auto">
          {isEn
            ? "An active Analyst Pass is required to run the Monte Carlo bankroll paths."
            : "运行蒙特卡洛资金路径模拟需要 Analyst 权限。"}
        </p>
        <button
          onClick={onOpenPricing}
          className="mt-5 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-xl shadow-lg shadow-blue-600/25 transition"
        >
          {monthlyPrice == null
            ? (isEn ? "Upgrade to Analyst Pass" : "开通 Analyst 专属通行证")
            : !Number.isFinite(monthlyPrice)
              ? (isEn ? "Upgrade to Analyst Pass (—)" : "开通 Analyst 专属通行证 (—)")
              : (isEn
                ? `Upgrade to Analyst Pass ($${Number.isInteger(monthlyPrice) ? monthlyPrice : monthlyPrice.toFixed(2)})`
                : `开通 Analyst 专属通行证 ($${Number.isInteger(monthlyPrice) ? monthlyPrice : monthlyPrice.toFixed(2)})`)}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
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

          <div className="bg-[#090d16] border border-gray-800/80 rounded-xl p-4 flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] font-mono text-gray-400 block mb-1">
                {isEn ? "Bankroll" : "本金规模"}
              </label>
              <input
                type="number"
                value={bankrollInput}
                onChange={(e) => setBankrollInput(e.target.value)}
                onBlur={() => {
                  const n = Number(bankrollInput);
                  if (!Number.isFinite(n) || n < 100) setBankrollInput("100");
                }}
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
                type="button"
                onClick={() => setRefreshNonce((n) => n + 1)}
                disabled={loading}
                aria-label={isEn ? "Run simulation again" : "重新模拟"}
                className="px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-bold text-xs flex items-center transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} />
                {isEn ? "Simulate" : "重新模拟"}
              </button>
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-sm text-red-300">
          {error}
        </div>
      )}

      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.expectedMedian")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              {fmtMoney(stats.expected_bankroll_median)}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">
              {isEn ? "Median Return" : "中位数收益"}: {fmtPct(stats.median_growth_pct, true)}
            </span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.doubleProb")}</span>
            <span className="text-xl sm:text-2xl font-black text-blue-400 mt-1 block">
              {fmtPct(stats.probability_doubling_pct)}
            </span>
            <span className="text-[10px] font-mono text-gray-400">
              {isEn ? "Reaching" : "达到"} {doubleTarget == null ? "—" : fmtMoney(doubleTarget * 2)}
            </span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.bestCase")}</span>
            <span className="text-xl sm:text-2xl font-black text-purple-400 mt-1 block">
              {fmtMoney(stats.best_case_p95)}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Upside Limit" : "顺风上限区间"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.worstCase")}</span>
            <span className="text-xl sm:text-2xl font-black text-amber-400 mt-1 block">
              {fmtMoney(stats.worst_case_p5)}
            </span>
            <span className="text-[10px] font-mono text-gray-400">{isEn ? "Extreme Drawdown" : "极端连黑抗压底线"}</span>
          </div>

          <div className="bg-[#0f1523] border border-gray-800 rounded-xl p-4">
            <span className="text-[11px] font-mono text-gray-400 block">{t("simulator.ruinRisk")}</span>
            <span className="text-xl sm:text-2xl font-black text-emerald-400 mt-1 block">
              {fmtPct(stats.risk_of_ruin_pct)}
            </span>
            <span className="text-[10px] font-mono text-emerald-500 font-bold">{isEn ? "Safe Half-Kelly Buffer" : "严格半凯利免爆仓"}</span>
          </div>
        </div>
      )}

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
