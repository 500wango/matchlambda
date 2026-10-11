"use client";

import React, { useState, useEffect, useRef } from "react";
import { Zap, TrendingUp, Shield, ArrowUpRight, ChevronRight } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useDebounced } from "@/lib/useDebounced";
import { useEligibleLeagues, isLeagueVisible } from "@/lib/leagueGate";
import { leagueShort } from "@/lib/leagues";

interface MatchHint {
  home?: string;
  away?: string;
  leagueId?: string;
  matchDate?: string;
}

interface AlphaScannerViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
  onSelectMatch: (matchId: string, hint?: MatchHint) => void;
}

function fmtOdds(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n.toFixed(2) : "—";
}

function fmtPct(value: unknown, digits = 1): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? `${(n * 100).toFixed(digits)}%` : "—";
}

// The scanner API already returns ev_pct / edge_pct / half_kelly_pct as
// percentage values (e.g. 5.2 means 5.2%), so they must not be re-scaled.
function fmtPercentValue(value: unknown, digits = 2): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? `${n.toFixed(digits)}%` : "—";
}

function fmtSignedPercentValue(value: unknown, digits = 2): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : ""}${n.toFixed(digits)}%`;
}

function fmtMoney(value: unknown, digits = 2): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? `$${n.toFixed(digits)}` : "—";
}

function fmtSignedMoney(value: unknown, digits = 2): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${n > 0 ? "+" : n < 0 ? "-" : ""}$${Math.abs(n).toFixed(digits)}`;
}

export const AlphaScannerView: React.FC<AlphaScannerViewProps> = ({
  isAnalyst,
  onOpenPricing,
  onSelectMatch,
}) => {
  const { lang, t } = useI18n();
  // Language only affects copy, never the request; keep it in a ref so a
  // language switch does not re-fire the scanner query.
  const langRef = useRef(lang);
  langRef.current = lang;
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Staking Inputs. Bankroll text can be cleared while typing; blur clamps it.
  const [bankrollInput, setBankrollInput] = useState("5000");
  const [strategy, setStrategy] = useState<string>("HALF_KELLY");
  const [minEv, setMinEv] = useState<number>(0.05);
  const [leagueFilter, setLeagueFilter] = useState<string>("ALL");
  const eligibleLeagues = useEligibleLeagues();
  const debouncedBankrollInput = useDebounced(bankrollInput, 400);
  const debouncedMinEv = useDebounced(minEv, 400);
  const bankrollForQuery = Number(debouncedBankrollInput);

  // PRD §2.1: drop the active filter when its league moves back to pending.
  useEffect(() => {
    if (leagueFilter !== "ALL" && !isLeagueVisible(leagueFilter, eligibleLeagues)) {
      setLeagueFilter("ALL");
    }
  }, [eligibleLeagues, leagueFilter]);

  const commitBankroll = () => {
    const n = Number(bankrollInput);
    const clamped = Number.isFinite(n) ? Math.max(10, n) : 10;
    setBankrollInput(String(clamped));
  };

  useEffect(() => {
    if (!isAnalyst) {
      setLoading(false);
      setSignals([]);
      return;
    }
    if (!Number.isFinite(bankrollForQuery) || bankrollForQuery < 10) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({
      min_ev: String(debouncedMinEv),
      bankroll: String(bankrollForQuery),
      strategy,
      limit: "40",
    });
    if (leagueFilter && leagueFilter !== "ALL") params.set("league_id", leagueFilter);
    apiRequest<any>(`/alpha/scanner?${params.toString()}`, { signal: controller.signal })
      .then((data) => {
        if (!active) return;
        setSignals(data?.signals || []);
      })
      .catch((err: any) => {
        if (!active || controller.signal.aborted || err?.code === "ABORTED") return;
        setError(err?.message || (langRef.current === "zh" ? "无法加载量化信号。" : "Failed to scan alpha signals."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort(new Error("Alpha scanner unmounted"));
    };
  }, [isAnalyst, bankrollForQuery, debouncedMinEv, strategy, leagueFilter]);

  const isEn = lang === "en";

  if (!isAnalyst) {
    return (
      <div className="border-y border-gray-800 py-12 text-center">
        <Shield className="w-8 h-8 text-emerald-400 mx-auto mb-3" />
        <h2 className="text-lg font-bold text-white">{isEn ? "Analyst scanner" : "Analyst 专属价值雷达"}</h2>
        <p className="text-sm text-gray-400 mt-2">{isEn ? "An active Analyst Pass is required to scan fresh quotes." : "扫描最新赔率需要有效 Analyst 权限。"}</p>
        <button onClick={onOpenPricing} className="mt-4 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold rounded-md">
          {isEn ? "View plans" : "查看套餐"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Hero Control Console */}
      <div className="bg-[#0f1523] border border-gray-800 rounded-2xl p-6 sm:p-7 shadow-2xl relative overflow-hidden">
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div>
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-3">
              <Zap className="w-3.5 h-3.5" />
              <span>{isEn ? "Latest eligible +EV market scanner" : "最新有效 +EV 市场价值雷达"}</span>
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
                  value={bankrollInput}
                  onChange={(e) => setBankrollInput(e.target.value)}
                  onBlur={commitBankroll}
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
                <option value={0.05}>EV ≥ +5.0% ({isEn ? "Recommended" : "建议"})</option>
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
            {["ALL", "TOP5", "EPL", "LA_LIGA", "SERIE_A", "BUNDESLIGA", "LIGUE_1", "UCL", "UEL", "ALLSVENSKAN", "ELITESERIEN", "SUPERLIGA", "AUSTRIAN_BUNDESLIGA", "CHAMPIONSHIP", "EREDIVISIE", "PRIMEIRA_LIGA", "MLS", "BRASILEIRAO", "SAUDI_PRO_LEAGUE"]
              .filter((l) => isLeagueVisible(l, eligibleLeagues))
              .map((l) => (
              <button
                key={l}
                type="button"
                aria-pressed={leagueFilter === l}
                onClick={() => setLeagueFilter(l)}
                className={`px-2.5 py-1 rounded-lg transition whitespace-nowrap ${
                  leagueFilter === l
                    ? "bg-blue-600 text-white font-bold"
                    : "bg-[#090d16] text-gray-400 hover:text-white border border-gray-800"
                }`}
              >
                {leagueShort(l)}
              </button>
            ))}
          </div>
        </div>

        {loading ? (
          <div className="py-24 text-center">
            <div className="w-10 h-10 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-xs text-gray-400 font-mono">
            {isEn ? "Checking current eligible predictions and quotes..." : "正在检查有效预测和赔率快照..."}
            </p>
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-400 font-mono text-xs">{error}</div>
        ) : signals.length === 0 ? (
          <div className="py-16 text-center text-gray-400">
            <p className="text-sm">{t("scanner.noSignals")}</p>
            <p className="text-xs text-gray-500 mt-1">
                {isEn ? "No eligible quote currently meets the selected EV threshold." : "当前没有赔率和预测同时有效、且达到所选 EV 门槛的信号。"}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-gray-800/80 bg-[#0a0e1a] text-gray-400 text-[11px]">
                  <th className="py-3 px-4">{isEn ? "Quote time" : "赔率时间"}</th>
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
                      {/* Quote freshness */}
                      <td className="py-3.5 px-4">
                        <span title={sig.quote_at} className="text-gray-300">
                          {new Date(sig.quote_at).toLocaleString(isEn ? "en-US" : "zh-CN", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
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
                          {fmtOdds(sig.market_odds)}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {isEn ? "Fair" : "公允"}: {fmtOdds(sig.fair_odds)} ({isEn ? "Win" : "胜率"} {fmtPct(sig.model_prob)})
                        </div>
                      </td>

                      {/* EV */}
                      <td className="py-3.5 px-4">
                        <span className="inline-flex items-center px-2 py-0.5 rounded font-black text-xs bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                          <ArrowUpRight className="w-3.5 h-3.5 mr-0.5" />
                          {fmtSignedPercentValue(sig.ev_pct, 1)}
                        </span>
                        <div className="text-[10px] text-gray-400 mt-0.5">
                          {t("scanner.edge")}: {fmtSignedPercentValue(sig.edge_pct)}
                        </div>
                      </td>

                      {/* Suggested Stake */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-white text-sm">
                          {fmtMoney(sig.suggested_stake)}
                        </div>
                        <div className="text-[10px] text-gray-400">
                          {fmtPercentValue(sig.half_kelly_pct)} {isEn ? "Bankroll" : "本金"}
                        </div>
                      </td>

                      {/* Expected Profit */}
                      <td className="py-3.5 px-4">
                        <div className="font-bold text-emerald-400 text-sm">
                          {fmtSignedMoney(sig.expected_profit)}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {isEn ? "Expected EV" : "按模型期望"}
                        </div>
                      </td>

                      {/* Action */}
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={() =>
                            onSelectMatch(sig.match_id, {
                              home: sig.home_team,
                              away: sig.away_team,
                              leagueId: sig.league_id,
                              matchDate: sig.match_date,
                            })
                          }
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
