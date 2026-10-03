"use client";

import React, { useState, useEffect, useCallback } from "react";
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

interface DailyPicksViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
  onSelectMatch: (matchId: string) => void;
}

const LEAGUE_LABELS: Record<string, { zh: string; en: string; badge: string }> = {
  EPL: { zh: "英超", en: "Premier League", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  LA_LIGA: { zh: "西甲", en: "La Liga", badge: "🇪🇸" },
  SERIE_A: { zh: "意甲", en: "Serie A", badge: "🇮🇹" },
  BUNDESLIGA: { zh: "德甲", en: "Bundesliga", badge: "🇩🇪" },
  LIGUE_1: { zh: "法甲", en: "Ligue 1", badge: "🇫🇷" },
  ALLSVENSKAN: { zh: "瑞超", en: "Allsvenskan", badge: "🇸🇪" },
  ELITESERIEN: { zh: "挪超", en: "Eliteserien", badge: "🇳🇴" },
  SUPERLIGA: { zh: "丹麦超", en: "Superliga", badge: "🇩🇰" },
  AUSTRIAN_BUNDESLIGA: { zh: "奥甲", en: "Austrian Bundesliga", badge: "🇦🇹" },
  CHAMPIONSHIP: { zh: "英冠", en: "Championship", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  EREDIVISIE: { zh: "荷甲", en: "Eredivisie", badge: "🇳🇱" },
  PRIMEIRA_LIGA: { zh: "葡超", en: "Primeira Liga", badge: "🇵🇹" },
  MLS: { zh: "美职联", en: "MLS", badge: "🇺🇸" },
  BRASILEIRAO: { zh: "巴西甲", en: "Brasileirão", badge: "🇧🇷" },
  SAUDI_PRO_LEAGUE: { zh: "沙特联", en: "Saudi Pro", badge: "🇸🇦" },
  UCL: { zh: "欧冠", en: "Champions League", badge: "⭐" },
  UEL: { zh: "欧联", en: "Europa League", badge: "🏆" },
};

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

  // Filter states
  const [selectedCategory, setSelectedCategory] = useState<
    "ALL" | "BANKER" | "VALUE" | "UNDERDOG" | "GOALS" | "PARLAYS"
  >("ALL");
  const [selectedLeague, setSelectedLeague] = useState<string>("ALL");

  const fetchPicks = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let query = `/picks/daily?days_ahead=10&lang=${lang}`;
      if (selectedLeague && selectedLeague !== "ALL") {
        query += `&league_id=${selectedLeague}`;
      }
      const res = await apiRequest<any>(query);
      setData(res);
    } catch (err: any) {
      setError(err?.message || (lang === "zh" ? "获取智能推荐失败，请重试。" : "Failed to load smart picks."));
    } finally {
      setLoading(false);
    }
  }, [selectedLeague, lang]);

  useEffect(() => {
    fetchPicks();
  }, [fetchPicks]);

  const handleCopyText = (id: string, text: string) => {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 2500);
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
    const seen = new Set();
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
            onClick={() => setSelectedCategory("PARLAYS")}
            className={`px-3.5 py-1.5 rounded-xl text-xs font-bold transition flex items-center space-x-1.5 ${
              selectedCategory === "PARLAYS"
                ? "bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-md shadow-blue-600/30"
                : "bg-gray-900/80 text-gray-400 hover:text-white border border-gray-800"
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5 text-blue-400" />
            <span>{t("picks.parlays")}</span>
            <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded-full font-mono">
              3
            </span>
          </button>

          <button
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
          ].map((l) => (
            <button
              key={l.id}
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
                                {parlay.combined_odds.toFixed(2)}x
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
                                key={idx}
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
                                    @{leg.odds.toFixed(2)}
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
                    const leagueName = lang === "zh" ? leagueObj?.zh || pick.league_id : leagueObj?.en || pick.league_id;
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
                              {Array.from({ length: pick.confidence_stars || 4 }).map((_, i) => (
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
                              {t("picks.expectedGoals")} {pick.expected_goals?.home || 1.0}
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
                              {t("picks.expectedGoals")} {pick.expected_goals?.away || 1.0}
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
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold text-xs">
                                @{pick.market_odds.toFixed(2)}
                              </span>
                            </div>
                          </div>

                          <div className="text-right">
                            <span className="text-[11px] text-gray-400 block mb-0.5">
                              {t("picks.modelVsFair")}
                            </span>
                            <div className="font-mono text-xs">
                              <span className="font-bold text-emerald-400">
                                {roundPct(pick.model_probability)}%
                              </span>
                              <span className="text-gray-500 ml-1">
                                ({t("picks.fair")} {pick.fair_odds.toFixed(2)})
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Top Predicted Exact Scores */}
                        {pick.top_scores && pick.top_scores.length > 0 && (
                          <div className="flex items-center justify-between text-xs py-2 px-3 rounded-lg bg-gray-900/40 border border-gray-800/60 font-mono">
                            <span className="text-gray-400 text-[11px]">{t("picks.topScores")}</span>
                            <div className="flex items-center space-x-2">
                              {pick.top_scores.map((s: any, idx: number) => (
                                <span
                                  key={idx}
                                  className="px-2 py-0.5 rounded bg-gray-800/80 text-gray-200 text-[11px]"
                                >
                                  <strong>{s.score}</strong> ({s.prob_pct}%)
                                </span>
                              ))}
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
                            {pick.key_stats?.map((stat: string, idx: number) => (
                              <span
                                key={idx}
                                className="text-[10px] px-2 py-0.5 rounded bg-gray-900 text-gray-400 border border-gray-800 font-mono"
                              >
                                {stat}
                              </span>
                            ))}
                          </div>

                          <button
                            onClick={() => onSelectMatch(pick.match_id)}
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

function roundPct(val: number): string {
  return (val * 100).toFixed(1);
}
