"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  Sparkles,
  Shield,
  Zap,
  Flame,
  Bomb,
  Goal,
  Copy,
  Check,
  TrendingUp,
  Clock,
  ChevronRight,
  Filter,
  RefreshCw,
  Info,
  Calendar,
  Star,
  CheckCircle2,
  Share2,
} from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useEligibleLeagues, isLeagueVisible } from "@/lib/leagueGate";
import { LEAGUE_LABELS, leagueLabel } from "@/lib/leagues";

interface MatchHint {
  home?: string;
  away?: string;
  leagueId?: string;
  matchDate?: string;
}

interface DailyPicksViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
  onSelectMatch: (matchId: string, hint?: MatchHint) => void;
}

function fmtOdds(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  return Number.isFinite(n) ? n.toFixed(2) : "—";
}

function formatModelPct(value: unknown): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

export const DailyPicksView: React.FC<DailyPicksViewProps> = ({
  isAnalyst,
  onOpenPricing,
  onSelectMatch,
}) => {
  const { lang, t } = useI18n();
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [copyError, setCopyError] = useState<string | null>(null);
  const copyTimer = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const seqRef = useRef(0);

  // Filter states
  const [selectedCategory, setSelectedCategory] = useState<
    "ALL" | "BANKER" | "VALUE" | "UNDERDOG" | "GOALS" | "PARLAYS"
  >("ALL");
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");
  const eligibleLeagues = useEligibleLeagues();

  // PRD §2.1: a league reverting to pending clears a stale local selection.
  useEffect(() => {
    if (selectedLeague !== "ALL" && !isLeagueVisible(selectedLeague, eligibleLeagues)) {
      setSelectedLeague("ALL");
    }
  }, [eligibleLeagues, selectedLeague]);

  const fetchPicks = useCallback(async () => {
    abortRef.current?.abort(new Error("Superseded"));
    const controller = new AbortController();
    abortRef.current = controller;
    const seq = ++seqRef.current;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ days_ahead: "10", lang });
      if (selectedLeague && selectedLeague !== "ALL") params.set("league_id", selectedLeague);
      const res = await apiRequest<any>(`/picks/daily?${params.toString()}`, {
        signal: controller.signal,
      });
      if (seq !== seqRef.current) return;
      setData(res);
    } catch (err: any) {
      if (seq !== seqRef.current || controller.signal.aborted || err?.code === "ABORTED") return;
      setError(err?.message || (lang === "zh" ? "获取智能推荐失败，请重试。" : "Failed to load smart picks."));
    } finally {
      if (seq === seqRef.current) setLoading(false);
    }
  }, [selectedLeague, lang]);

  useEffect(() => {
    fetchPicks();
    return () => {
      seqRef.current += 1;
      abortRef.current?.abort(new Error("Component unmounted"));
    };
  }, [fetchPicks]);

  useEffect(() => {
    return () => {
      if (copyTimer.current != null) window.clearTimeout(copyTimer.current);
    };
  }, []);

  const handleCopyText = async (id: string, text: string) => {
    try {
      if (!navigator.clipboard?.writeText) throw new Error("clipboard");
      await navigator.clipboard.writeText(text);
      setCopyError(null);
      setCopiedId(id);
      if (copyTimer.current != null) window.clearTimeout(copyTimer.current);
      copyTimer.current = window.setTimeout(() => setCopiedId(null), 2500);
    } catch {
      setCopyError(t("picks.copyFailed"));
    }
  };

  const getFilteredPicks = () => {
    if (!data) return [];
    if (selectedCategory === "BANKER") return data.bankers || [];
    if (selectedCategory === "VALUE") return data.values || [];
    if (selectedCategory === "UNDERDOG") return data.underdogs || [];
    if (selectedCategory === "GOALS") return data.goals || [];
    if (selectedCategory === "PARLAYS") return [];

    const allList = [
      ...(data.bankers || []),
      ...(data.values || []),
      ...(data.goals || []),
      ...(data.underdogs || []),
    ];
    const seen = new Set<string>();
    return allList.filter((item) => {
      if (seen.has(item.pick_id)) return false;
      seen.add(item.pick_id);
      return true;
    });
  };

  const filteredPicks = getFilteredPicks();

  return (
    <div className="space-y-8">
      {/* Top Banner & Introduction */}
      <div className="bg-gradient-to-r from-emerald-950/40 via-blue-950/30 to-purple-950/40 border border-emerald-500/20 rounded-2xl p-6 sm:p-8 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2 max-w-2xl">
            <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/20 border border-emerald-500/40 text-emerald-300 text-xs font-bold uppercase tracking-wider">
              <Sparkles className="w-3.5 h-3.5 animate-pulse" />
              <span>{t("picks.bannerBadge")}</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              {t("picks.bannerTitle")}
            </h2>
            <p className="text-sm text-gray-300 leading-relaxed">
              {t("picks.bannerDesc")}
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            <button
              onClick={fetchPicks}
              disabled={loading}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-gray-900/80 hover:bg-gray-800 border border-gray-700 text-xs font-bold text-gray-200 transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-400" : ""}`} />
              <span>{t("picks.refreshBtn")}</span>
            </button>
          </div>
        </div>

        {/* Category Filter Pills */}
        <div className="mt-6 pt-5 border-t border-gray-800/80 flex flex-wrap items-center gap-2">
          <button
            type="button"
            aria-pressed={selectedCategory === "ALL"}
            onClick={() => setSelectedCategory("ALL")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "ALL"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <span>{t("picks.all")}</span>
            {data?.summary && (
              <span className="text-[10px] bg-black/30 px-1.5 py-0.5 rounded-full">
                {filteredPicks.length}
              </span>
            )}
          </button>

          <button
            type="button"
            aria-pressed={selectedCategory === "PARLAYS"}
            onClick={() => setSelectedCategory("PARLAYS")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "PARLAYS"
                ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
            <span>{t("picks.parlays")}</span>
            {(data?.parlays?.length ?? 0) > 0 && (
              <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded-full font-mono">
                {data.parlays.length}
              </span>
            )}
          </button>

          <button
            type="button"
            aria-pressed={selectedCategory === "BANKER"}
            onClick={() => setSelectedCategory("BANKER")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "BANKER"
                ? "bg-emerald-600 text-white shadow-md shadow-emerald-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <Shield className="w-3.5 h-3.5 text-emerald-400" />
            <span>{t("picks.banker")}</span>
            <span className="text-[10px] bg-emerald-500/20 text-emerald-300 px-1.5 py-0.5 rounded-full font-mono">
              {data?.summary?.banker_count || 0}
            </span>
          </button>

          <button
            type="button"
            aria-pressed={selectedCategory === "VALUE"}
            onClick={() => setSelectedCategory("VALUE")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "VALUE"
                ? "bg-amber-600 text-white shadow-md shadow-amber-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <Flame className="w-3.5 h-3.5 text-amber-400" />
            <span>{t("picks.value")}</span>
            <span className="text-[10px] bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded-full font-mono">
              {data?.summary?.value_count || 0}
            </span>
          </button>

          <button
            type="button"
            aria-pressed={selectedCategory === "GOALS"}
            onClick={() => setSelectedCategory("GOALS")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "GOALS"
                ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <Goal className="w-3.5 h-3.5 text-purple-400" />
            <span>{t("picks.goals")}</span>
            <span className="text-[10px] bg-purple-500/20 text-purple-300 px-1.5 py-0.5 rounded-full font-mono">
              {data?.summary?.goals_count || 0}
            </span>
          </button>

          <button
            type="button"
            aria-pressed={selectedCategory === "UNDERDOG"}
            onClick={() => setSelectedCategory("UNDERDOG")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "UNDERDOG"
                ? "bg-rose-600 text-white shadow-md shadow-rose-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <Bomb className="w-3.5 h-3.5 text-rose-400" />
            <span>{t("picks.underdog")}</span>
            <span className="text-[10px] bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded-full font-mono">
              {data?.summary?.underdog_count || 0}
            </span>
          </button>
        </div>
      </div>

      {/* League Quick Filters */}
      <div className="flex items-center justify-between overflow-x-auto pb-1 scrollbar-none text-xs">
        <div className="flex items-center space-x-2">
          <span className="text-gray-400 font-bold flex items-center space-x-1 mr-1">
            <Filter className="w-3.5 h-3.5 text-gray-500" />
            <span>{t("picks.leagueScope")}</span>
          </span>
          {[
            { id: "ALL", name: t("leagues.all") },
            { id: "TOP5", name: t("leagues.top5") },
            { id: "EPL", name: t("leagues.epl") },
            { id: "LA_LIGA", name: t("leagues.laLiga") },
            { id: "SERIE_A", name: t("leagues.serieA") },
            { id: "BUNDESLIGA", name: t("leagues.bundesliga") },
            { id: "LIGUE_1", name: t("leagues.ligue1") },
            { id: "CUPS", name: t("leagues.cups") },
            { id: "NORDIC", name: t("leagues.nordic") },
          ]
            .filter((l) => isLeagueVisible(l.id, eligibleLeagues))
            .map((l) => (
            <button
              key={l.id}
              type="button"
              aria-pressed={selectedLeague === l.id}
              onClick={() => setSelectedLeague(l.id)}
              className={`px-3 py-1.5 rounded-lg font-semibold transition whitespace-nowrap ${
                selectedLeague === l.id
                  ? "bg-blue-600/30 text-blue-300 border border-blue-500/40"
                  : "bg-gray-900 text-gray-400 hover:text-gray-200 border border-gray-800"
              }`}
            >
              {l.name}
            </button>
          ))}
        </div>
      </div>

      {/* Loading & Error States */}
      {loading && (
        <div className="py-20 text-center space-y-4">
          <div className="w-10 h-10 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-gray-400 text-sm">{t("picks.loading")}</p>
        </div>
      )}

      {error && (
        <div className="p-6 bg-red-950/20 border border-red-500/30 rounded-2xl text-center space-y-3">
          <p className="text-red-400 font-bold">{error}</p>
          <button
            onClick={fetchPicks}
            className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-300 text-xs font-bold rounded-lg transition"
          >
            {t("picks.refreshBtn")}
          </button>
        </div>
      )}

      {copyError && (
        <p className="text-xs text-red-400">{copyError}</p>
      )}

      {!loading && !error && (
        <>
          {/* Section 1: Smart Parlays Showcase */}
          {(selectedCategory === "ALL" || selectedCategory === "PARLAYS") &&
            data?.parlays &&
            data.parlays.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="w-5 h-5 text-blue-400" />
                    <h3 className="text-lg font-extrabold text-white">
                      {t("picks.parlayTitle")}
                    </h3>
                  </div>
                  <span className="text-xs text-gray-400">
                    {t("picks.parlaySubtitle")}
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  {data.parlays.map((parlay: any) => {
                    const isCopied = copiedId === parlay.parlay_id;
                    const isSafe = parlay.type === "SAFE_2X1";
                    const isBalanced = parlay.type === "BALANCED_3X1";

                    return (
                      <div
                        key={parlay.parlay_id}
                        className={`rounded-2xl p-6 relative flex flex-col justify-between border transition shadow-xl ${
                          isSafe
                            ? "bg-gradient-to-b from-[#0b1720] to-[#0e1b26] border-emerald-500/40 hover:border-emerald-500"
                            : isBalanced
                            ? "bg-gradient-to-b from-[#0f172a] to-[#121c33] border-blue-500/40 hover:border-blue-500"
                            : "bg-gradient-to-b from-[#1c140d] to-[#241a12] border-amber-500/40 hover:border-amber-500"
                        }`}
                      >
                        {/* Ticket Badge */}
                        <div className="flex items-center justify-between mb-4">
                          <span
                            className={`px-2.5 py-1 rounded-md text-[11px] font-extrabold uppercase tracking-wider ${
                              isSafe
                                ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                                : isBalanced
                                ? "bg-blue-500/20 text-blue-300 border border-blue-500/40"
                                : "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                            }`}
                          >
                            {parlay.badge}
                          </span>
                          <span className="text-[11px] font-mono text-gray-400">
                            {t("picks.estWinRate")}{" "}
                            <strong className="text-white">{parlay.win_probability_pct}%</strong>
                          </span>
                        </div>

                        {/* Title & Return */}
                        <div className="space-y-1 mb-5">
                          <h4 className="font-extrabold text-white text-base leading-tight">
                            {parlay.title}
                          </h4>
                          <p className="text-xs text-gray-400">{parlay.subtitle}</p>

                          <div className="pt-3 flex items-baseline justify-between font-mono">
                            <div>
                              <span className="text-xs text-gray-400 block">{t("picks.combOdds")}</span>
                              <span
                                className={`text-2xl font-black ${
                                  isSafe
                                    ? "text-emerald-400"
                                    : isBalanced
                                    ? "text-blue-400"
                                    : "text-amber-400"
                                }`}
                              >
                                {fmtOdds(parlay.combined_odds)}x
                              </span>
                            </div>
                            <div className="text-right">
                              <span className="text-xs text-gray-400 block">
                                {t("picks.stakeReturn", { unit: parlay.suggested_unit })}
                              </span>
                              <span className="text-lg font-extrabold text-white">
                                ¥{parlay.expected_return}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Legs Details */}
                        <div className="space-y-2 py-3 border-t border-b border-gray-800/80 mb-5">
                          <div className="text-[11px] font-mono font-bold text-gray-400 mb-1">
                            {t("picks.includedLegs")} ({parlay.legs.length}):
                          </div>
                          {parlay.legs.map((leg: any, idx: number) => {
                            const leagueBadge = LEAGUE_LABELS[leg.league_id]?.badge || "⚽";
                            return (
                              <div
                                key={leg.match_id ?? `${leg.home_team}-${leg.away_team}-${idx}`}
                                className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-black/30 border border-gray-800/60"
                              >
                                <div className="space-y-0.5 truncate mr-2">
                                  <div className="flex items-center space-x-1.5 text-gray-300 font-bold truncate">
                                    <span>{leagueBadge}</span>
                                    <span className="truncate">
                                      {leg.home_team} vs {leg.away_team}
                                    </span>
                                  </div>
                                  <div className="text-[11px] text-gray-400">
                                    {t("picks.recLabel")}{" "}
                                    <span className="text-emerald-300 font-bold">{leg.selection}</span>
                                  </div>
                                </div>
                                <div className="text-right flex-shrink-0">
                                  <span className="px-2 py-0.5 rounded bg-gray-800 text-white font-mono font-bold">
                                    @{fmtOdds(leg.odds)}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>

                        {/* Action buttons */}
                        <div className="space-y-2">
                          <button
                            onClick={() => handleCopyText(parlay.parlay_id, parlay.copy_text)}
                            className={`w-full py-2.5 px-4 rounded-xl text-xs font-extrabold flex items-center justify-center space-x-2 transition shadow-md ${
                              isCopied
                                ? "bg-emerald-600 text-white"
                                : isSafe
                                ? "bg-emerald-600/90 hover:bg-emerald-500 text-white"
                                : isBalanced
                                ? "bg-blue-600/90 hover:bg-blue-500 text-white"
                                : "bg-amber-600/90 hover:bg-amber-500 text-white"
                            }`}
                          >
                            {isCopied ? (
                              <>
                                <Check className="w-4 h-4" />
                                <span>{t("picks.copied")}</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-4 h-4" />
                                <span>{t("picks.copyBtn")}</span>
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

          {/* Section 2: Curated Match Cards List */}
          {selectedCategory !== "PARLAYS" && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <Sparkles className="w-5 h-5 text-emerald-400" />
                  <h3 className="text-lg font-extrabold text-white">
                    {t("picks.singleSectionTitle")}
                  </h3>
                </div>
                <span className="text-xs text-gray-400">
                  {t("picks.totalAnalyses", { count: filteredPicks.length })}
                </span>
              </div>

              {filteredPicks.length === 0 ? (
                <div className="p-12 text-center bg-[#111726] border border-gray-800 rounded-2xl space-y-2">
                  <p className="text-gray-400 text-sm">{t("picks.noPicks")}</p>
                  <button
                    onClick={() => {
                      setSelectedLeague("ALL");
                      setSelectedCategory("ALL");
                    }}
                    className="text-xs text-blue-400 font-bold hover:underline"
                  >
                    {t("picks.viewAllLeagues")}
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {filteredPicks.map((pick: any) => {
                    const leagueObj = LEAGUE_LABELS[pick.league_id];
                    const leagueBadge = leagueObj?.badge || "⚽";
                    const leagueName = leagueLabel(pick.league_id, lang === "zh" ? "zh" : "en");
                    const matchDate = new Date(pick.match_date);
                    const dateFormatted = matchDate.toLocaleDateString(lang === "zh" ? "zh-CN" : "en-US", {
                      month: "numeric",
                      day: "numeric",
                      weekday: "short",
                    });
                    const timeFormatted = matchDate.toLocaleTimeString(lang === "zh" ? "zh-CN" : "en-US", {
                      hour: "2-digit",
                      minute: "2-digit",
                    });

                    const isBanker = pick.category === "BANKER";
                    const isValue = pick.category === "VALUE";
                    const isGoals = pick.category === "GOALS";

                    return (
                      <div
                        key={pick.pick_id}
                        className="bg-[#111726] border border-gray-800/80 hover:border-gray-700/80 rounded-2xl p-6 transition shadow-xl flex flex-col justify-between space-y-5"
                      >
                        {/* Header: Badge, League, Kickoff Time, Stars */}
                        <div className="flex items-center justify-between pb-3 border-b border-gray-800/80 text-xs">
                          <div className="flex items-center space-x-2">
                            <span
                              className={`px-2.5 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                                isBanker
                                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                                  : isValue
                                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                                  : isGoals
                                  ? "bg-purple-500/20 text-purple-300 border border-purple-500/40"
                                  : "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                              }`}
                            >
                              {pick.category_label}
                            </span>
                            <span className="font-semibold text-gray-300 flex items-center space-x-1">
                              <span>{leagueBadge}</span>
                              <span>{leagueName}</span>
                            </span>
                          </div>

                          <div className="flex items-center space-x-3 text-gray-400">
                            <div className="flex items-center text-amber-400">
                              {Array.from({ length: pick.confidence_stars ?? 4 }).map((_, i) => (
                                <Star key={i} className="w-3.5 h-3.5 fill-current" />
                              ))}
                            </div>
                            <div className="flex items-center space-x-1 font-mono text-[11px]">
                              <Clock className="w-3 h-3 text-gray-500" />
                              <span>
                                {dateFormatted} {timeFormatted}
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Match Fixture */}
                        <div className="flex items-center justify-between px-2">
                          <div className="w-5/12 text-left">
                            <h4 className="font-bold text-white text-base truncate">
                              {pick.home_team}
                            </h4>
                            <span className="text-[11px] text-gray-500 font-mono">
                              {t("picks.expectedGoals")} {pick.expected_goals?.home ?? 1.0}
                            </span>
                          </div>
                          <div className="w-2/12 text-center text-xs font-mono font-bold text-gray-400 bg-gray-900/60 py-1 rounded">
                            VS
                          </div>
                          <div className="w-5/12 text-right">
                            <h4 className="font-bold text-white text-base truncate">
                              {pick.away_team}
                            </h4>
                            <span className="text-[11px] text-gray-500 font-mono">
                              {t("picks.expectedGoals")} {pick.expected_goals?.away ?? 1.0}
                            </span>
                          </div>
                        </div>

                        {/* Recommendation Highlight Box */}
                        <div className="p-4 rounded-xl bg-gradient-to-r from-gray-900/90 to-gray-950 border border-gray-800/80 flex items-center justify-between">
                          <div>
                            <span className="text-[11px] text-gray-400 block mb-0.5">
                              {t("picks.recMarket")}
                            </span>
                            <div className="flex items-center space-x-2">
                              <span className="text-base font-extrabold text-white">
                                {pick.selection_name}
                              </span>
                              {pick.market_odds == null ? (
                                <span className="text-[10px] text-gray-400">{t("picks.modelEstimateOnly")}</span>
                              ) : (
                                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold text-xs">
                                  @{fmtOdds(pick.market_odds)}
                                </span>
                              )}
                            </div>
                          </div>

                          <div className="text-right">
                            <span className="text-[11px] text-gray-400 block mb-0.5">
                              {t("picks.modelVsFair")}
                            </span>
                            <div className="font-mono text-xs">
                              <span className="font-bold text-emerald-400">
                                {formatModelPct(pick.model_probability)}
                              </span>
                              <span className="text-gray-500 ml-1">
                                ({t("picks.fair")} {fmtOdds(pick.fair_odds)})
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Over/Under Visual Distribution Split */}
                        {(() => {
                          const isTotalsPick =
                            isGoals ||
                            pick.selection === "OVER_2_5" ||
                            pick.selection?.includes("OVER") ||
                            pick.selection?.includes("UNDER") ||
                            pick.market_type?.toLowerCase().includes("totals") ||
                            pick.market_type?.includes("大小");

                          if (!isTotalsPick) return null;

                          const isOverPick = pick.selection?.includes("OVER") ?? true;
                          const modelProb =
                            typeof pick.model_probability === "number"
                              ? pick.model_probability
                              : Number(pick.model_probability) || 0.5;
                          const underProbVal =
                            typeof pick.under_probability === "number"
                              ? pick.under_probability
                              : isOverPick
                              ? Math.max(0, 1 - modelProb)
                              : modelProb;
                          const overProbVal = isOverPick ? modelProb : Math.max(0, 1 - underProbVal);

                          const overPct = (overProbVal * 100).toFixed(1);
                          const underPct = (underProbVal * 100).toFixed(1);

                          return (
                            <div className="p-3.5 rounded-xl bg-gray-900/60 border border-gray-800/80 space-y-2">
                              <div className="flex items-center justify-between text-xs">
                                <div className="flex items-center space-x-1.5 font-mono">
                                  <span className="w-2 h-2 rounded-full bg-blue-400"></span>
                                  <span className="text-gray-300 font-medium">{t("picks.under25")}</span>
                                  <span className="text-blue-300 font-bold">{underPct}%</span>
                                </div>
                                <div className="flex items-center space-x-1.5 font-mono">
                                  <span className="text-emerald-400 font-bold">{t("picks.over25")}</span>
                                  <span className="text-emerald-300 font-extrabold">{overPct}%</span>
                                  <span className="w-2 h-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]"></span>
                                </div>
                              </div>

                              {/* Dual Progress Bar */}
                              <div className="h-2.5 w-full bg-gray-950 rounded-full overflow-hidden flex border border-gray-800/80">
                                <div
                                  className="h-full bg-gradient-to-r from-blue-600 to-blue-500 transition-all duration-500"
                                  style={{ width: `${underPct}%` }}
                                  title={`${t("picks.under25")}: ${underPct}%`}
                                />
                                <div
                                  className="h-full bg-gradient-to-r from-emerald-500 to-teal-400 transition-all duration-500 shadow-[0_0_10px_rgba(16,185,129,0.3)]"
                                  style={{ width: `${overPct}%` }}
                                  title={`${t("picks.over25")}: ${overPct}%`}
                                />
                              </div>

                              <div className="flex items-center justify-between text-[10px] text-gray-500 font-mono pt-0.5">
                                <span>{t("picks.under25Detail")}</span>
                                <span className="text-emerald-400/90 font-medium">{t("picks.over25Detail")}</span>
                              </div>
                            </div>
                          );
                        })()}

                        {/* Top Predicted Exact Scores (Statistical Modes) */}
                        {pick.top_scores && pick.top_scores.length > 0 && (
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs py-2 px-3 rounded-lg bg-gray-900/40 border border-gray-800/60 font-mono">
                            <div
                              className="flex items-center space-x-1.5 text-gray-400 text-[11px]"
                              title={t("picks.topScoresHint")}
                            >
                              <Info className="w-3 h-3 text-gray-500" />
                              <span>{t("picks.topScores")}</span>
                            </div>
                            <div className="flex items-center space-x-1.5 flex-wrap gap-y-1">
                              {pick.top_scores.map((s: any, idx: number) => {
                                let goals: number | null = typeof s.goals === "number" ? s.goals : null;
                                if (goals === null && typeof s.score === "string" && s.score.includes("-")) {
                                  const parts = s.score.split("-");
                                  if (parts.length === 2 && !isNaN(Number(parts[0])) && !isNaN(Number(parts[1]))) {
                                    goals = Number(parts[0]) + Number(parts[1]);
                                  }
                                }
                                const isTotalsPick =
                                  isGoals ||
                                  pick.selection === "OVER_2_5" ||
                                  pick.selection?.includes("OVER");
                                const isOverLine = isTotalsPick && goals !== null && goals >= 3;

                                return (
                                  <span
                                    key={s.score ?? `score-${idx}`}
                                    className={`px-2 py-0.5 rounded text-[11px] inline-flex items-center space-x-1 border ${
                                      isOverLine
                                        ? "bg-emerald-950/60 border-emerald-600/50 text-emerald-300 font-semibold"
                                        : "bg-gray-800/80 border-gray-700/60 text-gray-300"
                                    }`}
                                  >
                                    <strong>{s.score}</strong>
                                    <span className={isOverLine ? "text-emerald-400/80" : "text-gray-400"}>
                                      ({s.prob_pct}%)
                                    </span>
                                    {goals !== null && (
                                      <span
                                        className={`text-[9px] px-1 py-0.2 rounded font-sans ${
                                          isOverLine
                                            ? "bg-emerald-500/20 text-emerald-300"
                                            : "bg-gray-700/60 text-gray-400"
                                        }`}
                                      >
                                        {goals}
                                        {t("picks.goalsSuffix")}
                                      </span>
                                    )}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* AI Rationale Paragraph */}
                        <div className="p-3.5 rounded-xl bg-[#0c101c] border border-gray-800/60 space-y-1.5">
                          <div className="flex items-center space-x-1.5 text-xs font-bold text-emerald-400">
                            <Sparkles className="w-3.5 h-3.5" />
                            <span>{t("picks.aiRationale")}</span>
                          </div>
                          <p className="text-xs text-gray-300 leading-relaxed">
                            {pick.reasoning}
                          </p>
                        </div>

                        {/* Footer: View Full 6x6 Matrix */}
                        <div className="pt-2 flex items-center justify-between">
                          <div className="flex items-center space-x-2">
                            {pick.key_stats?.map((stat: string) => (
                              <span
                                key={stat}
                                className="text-[10px] px-2 py-0.5 rounded bg-gray-900 text-gray-400 border border-gray-800 font-mono"
                              >
                                {stat}
                              </span>
                            ))}
                          </div>

                          <button
                            onClick={() =>
                              onSelectMatch(pick.match_id, {
                                home: pick.home_team,
                                away: pick.away_team,
                                leagueId: pick.league_id,
                                matchDate: pick.match_date,
                              })
                            }
                            className="inline-flex items-center space-x-1 text-xs font-bold text-blue-400 hover:text-blue-300 transition"
                          >
                            <span>{t("picks.matrixBtn")}</span>
                            <ChevronRight className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
};

