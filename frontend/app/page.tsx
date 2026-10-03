"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { FixtureCard } from "@/components/FixtureCard";
import { AuthModal } from "@/components/AuthModal";
import { PricingModal } from "@/components/PricingModal";
import { AnalysisModal } from "@/components/AnalysisModal";
import { AlphaScannerView } from "@/components/AlphaScannerView";
import { BacktestView } from "@/components/BacktestView";
import { BankrollSimulatorView } from "@/components/BankrollSimulatorView";
import { DailyPicksView } from "@/components/DailyPicksView";
import { apiRequest, setAuthToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Shield, Sparkles, Filter, RefreshCw, Calendar, AlertCircle, Trophy, Zap, TrendingUp, Calculator, BarChart3 } from "lucide-react";

interface LeagueOption {
  id: string;
  name: string;
  country: string;
  badge: string;
}

interface LeagueCategory {
  category: string;
  groupOption: LeagueOption;
  leagues: LeagueOption[];
}

const LEAGUE_CATEGORIES: LeagueCategory[] = [
  {
    category: "五大联赛",
    groupOption: { id: "TOP5", name: "全部五大联赛 (All Top 5)", country: "Europe", badge: "🏆" },
    leagues: [
      { id: "EPL", name: "Premier League (英超)", country: "England", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
      { id: "LA_LIGA", name: "La Liga (西甲)", country: "Spain", badge: "🇪🇸" },
      { id: "SERIE_A", name: "Serie A (意甲)", country: "Italy", badge: "🇮🇹" },
      { id: "BUNDESLIGA", name: "Bundesliga (德甲)", country: "Germany", badge: "🇩🇪" },
      { id: "LIGUE_1", name: "Ligue 1 (法甲)", country: "France", badge: "🇫🇷" },
    ],
  },
  {
    category: "北欧与中欧联赛",
    groupOption: { id: "NORDIC", name: "全部北欧与中欧", country: "Europe", badge: "❄️" },
    leagues: [
      { id: "ALLSVENSKAN", name: "瑞超 (Allsvenskan)", country: "Sweden", badge: "🇸🇪" },
      { id: "ELITESERIEN", name: "挪超 (Eliteserien)", country: "Norway", badge: "🇳🇴" },
      { id: "SUPERLIGA", name: "丹麦超 (Superliga)", country: "Denmark", badge: "🇩🇰" },
      { id: "AUSTRIAN_BUNDESLIGA", name: "奥甲/奥超 (Bundesliga)", country: "Austria", badge: "🇦🇹" },
    ],
  },
  {
    category: "欧洲其他主要联赛",
    groupOption: { id: "EURO_OTHER", name: "全部其他主要联赛", country: "Europe", badge: "🌍" },
    leagues: [
      { id: "CHAMPIONSHIP", name: "英冠 (Championship)", country: "England", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
      { id: "EREDIVISIE", name: "荷甲 (Eredivisie)", country: "Netherlands", badge: "🇳🇱" },
      { id: "PRIMEIRA_LIGA", name: "葡超 (Primeira Liga)", country: "Portugal", badge: "🇵🇹" },
    ],
  },
  {
    category: "美洲及全球",
    groupOption: { id: "GLOBAL", name: "全部美洲及全球", country: "Global", badge: "🌎" },
    leagues: [
      { id: "MLS", name: "美职联 (MLS)", country: "USA", badge: "🇺🇸" },
      { id: "BRASILEIRAO", name: "巴西甲 (Brasileirão)", country: "Brazil", badge: "🇧🇷" },
      { id: "SAUDI_PRO_LEAGUE", name: "沙特联 (Saudi Pro)", country: "Saudi Arabia", badge: "🇸🇦" },
    ],
  },
  {
    category: "欧洲杯赛",
    groupOption: { id: "CUPS", name: "全部欧战杯赛", country: "Europe", badge: "⭐" },
    leagues: [
      { id: "UCL", name: "Champions League (欧冠)", country: "Europe", badge: "⭐" },
      { id: "UEL", name: "Europa League (欧联)", country: "Europe", badge: "🏆" },
    ],
  },
];

const ALL_LEAGUES: LeagueOption[] = LEAGUE_CATEGORIES.flatMap((c) => c.leagues);

const ALL_LEAGUE_MAP: Record<string, LeagueOption> = {
  TOP5: { id: "TOP5", name: "五大联赛 (Top 5 Leagues)", country: "Europe", badge: "🏆" },
  ALL: { id: "ALL", name: "全网所有联赛 (All 17 Leagues)", country: "Global", badge: "🌐" },
  NORDIC: { id: "NORDIC", name: "北欧与中欧联赛", country: "Europe", badge: "❄️" },
  CUPS: { id: "CUPS", name: "欧战顶级杯赛", country: "Europe", badge: "⭐" },
  EURO_OTHER: { id: "EURO_OTHER", name: "欧洲其他主要联赛", country: "Europe", badge: "🌍" },
  GLOBAL: { id: "GLOBAL", name: "美洲及全球联赛", country: "Global", badge: "🌎" },
};
for (const cat of LEAGUE_CATEGORIES) {
  for (const l of cat.leagues) {
    ALL_LEAGUE_MAP[l.id] = l;
  }
}

function HomeContent() {
  const { lang, t } = useI18n();
  const searchParams = useSearchParams();
  const [user, setUser] = useState<any | null>(null);
  const isAnalyst = user?.effective_plan === "ANALYST";
  const [selectedLeague, setSelectedLeague] = useState<string>("TOP5");
  const [activeCategory, setActiveCategory] = useState<string>("五大联赛");
  const [fixtures, setFixtures] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [daysAhead, setDaysAhead] = useState<number>(10);
  const [valueOnly, setValueOnly] = useState<boolean>(false);

  // Terminal Mode View: PICKS (default for casual users), SCANNER (alpha quant), FIXTURES, BACKTEST, SIMULATOR
  const [terminalTab, setTerminalTab] = useState<"PICKS" | "SCANNER" | "FIXTURES" | "BACKTEST" | "SIMULATOR">("PICKS");
  const [liveTickerSignals, setLiveTickerSignals] = useState<any[]>([]);

  // Modals
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [isPricingOpen, setIsPricingOpen] = useState<boolean>(false);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

  // Show the same entitlement-gated feed used by the scanner view.
  useEffect(() => {
    if (!isAnalyst) {
      setLiveTickerSignals([]);
      return;
    }
    apiRequest<any>("/alpha/scanner?min_ev=0.05&limit=4")
      .then((res) => setLiveTickerSignals(res.signals || []))
      .catch(() => setLiveTickerSignals([]));
  }, [isAnalyst]);

  // Auto open modal on return from NOWPayments hosted checkout
  useEffect(() => {
    const statusParam = searchParams.get("status");
    const orderIdParam = searchParams.get("order_id");
    if (statusParam && orderIdParam) {
      setIsPricingOpen(true);
    }
  }, [searchParams]);

  const fetchUser = useCallback(async () => {
    try {
      const data = await apiRequest<any>("/me");
      setUser(data);
    } catch {
      setUser(null);
    }
  }, []);

  const fetchFixtures = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      let query = `/matches/fixtures?days_ahead=${daysAhead}&limit=50&offset=0`;
      if (selectedLeague && selectedLeague !== "ALL") {
        query += `&league_id=${selectedLeague}`;
      }
      if (valueOnly && user?.effective_plan === "ANALYST") {
        query += "&has_value=true";
      }
      const data = await apiRequest<any>(query);
      setFixtures(data.fixtures || []);
      setTotal(data.total || 0);
    } catch (err: any) {
      setError(err?.message || "Failed to load fixtures.");
    } finally {
      setLoading(false);
    }
  }, [selectedLeague, daysAhead, valueOnly, user]);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  useEffect(() => {
    fetchFixtures();
  }, [fetchFixtures]);

  const handleLogout = () => {
    setAuthToken(null);
    setUser(null);
    setValueOnly(false);
    fetchFixtures();
  };

  const handleToggleValueFilter = () => {
    if (user?.effective_plan !== "ANALYST") {
      setIsPricingOpen(true);
      return;
    }
    setValueOnly(!valueOnly);
  };

  const currentLeagueObj = ALL_LEAGUE_MAP[selectedLeague] || {
    id: selectedLeague,
    name: selectedLeague,
    country: "Global",
    badge: "⚽",
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#080c14] text-gray-100">
      <Navbar
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenPricing={() => setIsPricingOpen(true)}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Latest eligible +EV signals */}
        {liveTickerSignals.length > 0 && (
          <div className="bg-emerald-950/20 border border-emerald-500/30 rounded-xl px-4 py-2.5 flex items-center justify-between overflow-hidden text-xs font-mono">
            <div className="flex items-center space-x-2 flex-shrink-0 mr-4 text-emerald-400 font-bold">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" />
              <span>{t("tabs.liveTicker")}</span>
            </div>
            <div className="flex items-center space-x-6 overflow-x-auto scrollbar-none whitespace-nowrap">
              {liveTickerSignals.map((sig) => (
                <button
                  key={sig.signal_id}
                  onClick={() => {
                    setTerminalTab("SCANNER");
                    setSelectedMatchId(sig.match_id);
                  }}
                  className="flex items-center space-x-2 hover:text-emerald-300 transition cursor-pointer"
                >
                  <span className="text-gray-400 font-bold">[{sig.league_id}]</span>
                  <span className="font-bold text-white">{sig.home_team} vs {sig.away_team}</span>
                  <span className="text-emerald-400 font-bold">({sig.selection_label})</span>
                  <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-bold">
                    +{sig.ev_pct}% EV
                  </span>
                  <span className="text-gray-400">{t("tabs.odds")} {sig.market_odds}</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Terminal Main Mode Switcher */}
        <div className="flex items-center justify-between border-b border-gray-800 pb-3">
          <div className="flex items-center space-x-2 overflow-x-auto scrollbar-none">
            <button
              onClick={() => setTerminalTab("PICKS")}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                terminalTab === "PICKS"
                  ? "bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-500/20 border border-emerald-400/40"
                  : "bg-[#0d121f] text-gray-400 hover:text-white border border-gray-800"
              }`}
            >
              <Sparkles className="w-4 h-4 text-emerald-300 animate-pulse" />
              <span>{t("tabs.picks")}</span>
            </button>

            <button
              onClick={() => setTerminalTab("SCANNER")}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                terminalTab === "SCANNER"
                  ? "bg-emerald-600 text-white shadow-lg shadow-emerald-500/20 border border-emerald-400/40"
                  : "bg-[#0d121f] text-gray-400 hover:text-white border border-gray-800"
              }`}
            >
              <Zap className="w-4 h-4 text-amber-300" />
              <span>{t("tabs.scanner")}</span>
            </button>

            <button
              onClick={() => setTerminalTab("FIXTURES")}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                terminalTab === "FIXTURES"
                  ? "bg-blue-600 text-white shadow-lg shadow-blue-500/20 border border-blue-400/40"
                  : "bg-[#0d121f] text-gray-400 hover:text-white border border-gray-800"
              }`}
            >
              <Trophy className="w-4 h-4 text-blue-300" />
              <span>{t("tabs.fixtures")}</span>
            </button>

            <button
              onClick={() => setTerminalTab("BACKTEST")}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                terminalTab === "BACKTEST"
                  ? "bg-purple-600 text-white shadow-lg shadow-purple-500/20 border border-purple-400/40"
                  : "bg-[#0d121f] text-gray-400 hover:text-white border border-gray-800"
              }`}
            >
              <TrendingUp className="w-4 h-4 text-purple-300" />
              <span>{t("tabs.backtest")}</span>
            </button>

            <button
              onClick={() => setTerminalTab("SIMULATOR")}
              className={`flex items-center space-x-2 px-4 py-2.5 rounded-xl text-xs font-bold transition whitespace-nowrap ${
                terminalTab === "SIMULATOR"
                  ? "bg-indigo-600 text-white shadow-lg shadow-indigo-500/20 border border-indigo-400/40"
                  : "bg-[#0d121f] text-gray-400 hover:text-white border border-gray-800"
              }`}
            >
              <Calculator className="w-4 h-4 text-indigo-300" />
              <span>{t("tabs.simulator")}</span>
            </button>
          </div>
        </div>

        {/* View Content Panels */}
        {terminalTab === "PICKS" && (
          <DailyPicksView
            isAnalyst={isAnalyst}
            onOpenPricing={() => setIsPricingOpen(true)}
            onSelectMatch={(id) => setSelectedMatchId(id)}
          />
        )}

        {terminalTab === "SCANNER" && (
          <AlphaScannerView
            isAnalyst={isAnalyst}
            onOpenPricing={() => setIsPricingOpen(true)}
            onSelectMatch={(id) => setSelectedMatchId(id)}
          />
        )}

        {terminalTab === "BACKTEST" && (
          <BacktestView
            isAnalyst={isAnalyst}
            onOpenPricing={() => setIsPricingOpen(true)}
          />
        )}

        {terminalTab === "SIMULATOR" && (
          <BankrollSimulatorView
            isAnalyst={isAnalyst}
            onOpenPricing={() => setIsPricingOpen(true)}
          />
        )}

        {terminalTab === "FIXTURES" && (
          <>
            {/* League Selector Group */}
            <div className="space-y-3 pb-3 border-b border-gray-800/80">
          {/* Category Tabs */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
            <button
              onClick={() => {
                setActiveCategory("五大联赛");
                setSelectedLeague("TOP5");
              }}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition ${
                activeCategory === "五大联赛"
                  ? "text-blue-400 bg-blue-950/60 border border-blue-600/40"
                  : "text-gray-400 hover:text-gray-200 bg-[#0d121f] border border-gray-800/60"
              }`}
            >
              🏆 五大联赛 (Top 5)
            </button>
            <button
              onClick={() => {
                setActiveCategory("全部联赛");
                setSelectedLeague("ALL");
              }}
              className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition ${
                activeCategory === "全部联赛"
                  ? "text-blue-400 bg-blue-950/60 border border-blue-600/40"
                  : "text-gray-400 hover:text-gray-200 bg-[#0d121f] border border-gray-800/60"
              }`}
            >
              🌐 全部联赛 ({ALL_LEAGUES.length})
            </button>
            {LEAGUE_CATEGORIES.filter((c) => c.category !== "五大联赛").map((cat) => {
              const isCatActive = cat.category === activeCategory;
              return (
                <button
                  key={cat.category}
                  onClick={() => {
                    setActiveCategory(cat.category);
                    setSelectedLeague(cat.groupOption.id);
                  }}
                  className={`text-xs font-semibold px-3 py-1.5 rounded-lg transition ${
                    isCatActive
                      ? "text-blue-400 bg-blue-950/60 border border-blue-600/40"
                      : "text-gray-400 hover:text-gray-200 bg-[#0d121f] border border-gray-800/60"
                  }`}
                >
                  {cat.category}
                </button>
              );
            })}
          </div>

          {/* League Pills for Active Category */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
            {activeCategory === "全部联赛" ? (
              <>
                <button
                  onClick={() => setSelectedLeague("ALL")}
                  className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-xs whitespace-nowrap transition ${
                    selectedLeague === "ALL"
                      ? "bg-blue-600 text-white font-bold shadow-lg shadow-blue-500/20 border border-blue-400/30"
                      : "bg-[#0d121f] text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800/80"
                  }`}
                >
                  <span className="text-base">🌐</span>
                  <span>全网所有赛事 (All 17 Leagues)</span>
                </button>
                {ALL_LEAGUES.map((league) => {
                  const isActive = selectedLeague === league.id;
                  return (
                    <button
                      key={league.id}
                      onClick={() => setSelectedLeague(league.id)}
                      className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-xs whitespace-nowrap transition ${
                        isActive
                          ? "bg-blue-600 text-white font-bold shadow-lg shadow-blue-500/20 border border-blue-400/30"
                          : "bg-[#0d121f] text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800/80"
                      }`}
                    >
                      <span className="text-base">{league.badge}</span>
                      <span>{league.name}</span>
                      <span className="text-[10px] opacity-75 font-mono">({league.id})</span>
                    </button>
                  );
                })}
              </>
            ) : (
              (() => {
                const curCat =
                  LEAGUE_CATEGORIES.find((c) => c.category === activeCategory) ||
                  LEAGUE_CATEGORIES[0];
                const list = [curCat.groupOption, ...curCat.leagues];
                return list.map((league) => {
                  const isActive = selectedLeague === league.id;
                  return (
                    <button
                      key={league.id}
                      onClick={() => setSelectedLeague(league.id)}
                      className={`flex items-center space-x-2 px-3.5 py-2 rounded-xl font-medium text-xs whitespace-nowrap transition ${
                        isActive
                          ? "bg-blue-600 text-white font-bold shadow-lg shadow-blue-500/20 border border-blue-400/30"
                          : "bg-[#0d121f] text-gray-400 hover:text-white hover:bg-gray-800 border border-gray-800/80"
                      }`}
                    >
                      <span className="text-base">{league.badge}</span>
                      <span>{league.name}</span>
                      <span className="text-[10px] opacity-75 font-mono">({league.id})</span>
                    </button>
                  );
                });
              })()
            )}
          </div>
        </div>

        {/* Hero Banner */}
        <div className="relative rounded-2xl bg-gradient-to-r from-blue-900/40 via-indigo-950/30 to-purple-900/20 border border-blue-500/20 p-6 sm:p-8 overflow-hidden shadow-2xl">
          <div className="relative z-10 max-w-2xl">
            <div className="inline-flex items-center space-x-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Dixon–Coles Time-Weighted Poisson Model</span>
            </div>
            <h1 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight flex items-center gap-3">
              <span>{currentLeagueObj.badge}</span>
              <span>{currentLeagueObj.name} Probability Engine</span>
            </h1>
            <p className="text-sm text-gray-400 mt-2 leading-relaxed">
              Reproducible goal expectations, full 6×6 score distribution tail matrices, and Shin
              de-juiced bookmaker comparisons for {currentLeagueObj.name} fixtures.
            </p>
          </div>

          <div className="mt-6 flex flex-wrap gap-4 text-xs font-mono text-gray-400 border-t border-gray-800/80 pt-4">
            <div>
              <span className="text-gray-500 block text-[10px]">TIME DECAY</span>
              <span className="text-white font-bold">ξ = 0.0018 / day</span>
            </div>
            <div className="border-l border-gray-800 pl-4">
              <span className="text-gray-500 block text-[10px]">ACTIVE LEAGUE</span>
              <span className="text-white font-bold">{currentLeagueObj.name}</span>
            </div>
            <div className="border-l border-gray-800 pl-4">
              <span className="text-gray-500 block text-[10px]">TARGET MARKET</span>
              <span className="text-white font-bold">Regulation 1X2</span>
            </div>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-[#0d121f] border border-gray-800/80 p-4 rounded-xl">
          <div className="flex items-center space-x-3">
            <span className="text-xs font-medium text-gray-400 flex items-center">
              <Calendar className="w-3.5 h-3.5 mr-1.5 text-blue-400" /> Kickoff Window:
            </span>
            <div className="flex items-center bg-[#070b13] border border-gray-800 rounded-lg p-1 text-xs">
              {[3, 7, 10, 14].map((days) => (
                <button
                  key={days}
                  onClick={() => setDaysAhead(days)}
                  className={`px-3 py-1 rounded-md transition font-medium ${
                    daysAhead === days
                      ? "bg-blue-600 text-white font-bold"
                      : "text-gray-400 hover:text-white"
                  }`}
                >
                  {days}d
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Value Bets Only Filter */}
            <button
              onClick={handleToggleValueFilter}
              className={`flex items-center text-xs px-3.5 py-2 rounded-lg border font-medium transition ${
                valueOnly
                  ? "bg-emerald-500/20 border-emerald-500/40 text-emerald-300"
                  : "bg-[#070b13] border-gray-800 text-gray-400 hover:text-white"
              }`}
            >
              <Filter className="w-3.5 h-3.5 mr-1.5" />
              <span>Value Bets (EV ≥ 5%)</span>
              {!isAnalyst && <Shield className="w-3 h-3 ml-2 text-blue-400" />}
            </button>

            <button
              onClick={fetchFixtures}
              disabled={loading}
              className="p-2 text-gray-400 hover:text-white bg-[#070b13] border border-gray-800 rounded-lg transition"
              title="Refresh fixtures"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        {/* Fixtures Grid */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-bold text-white tracking-tight flex items-center gap-2">
              <span>{currentLeagueObj.badge}</span>
              <span>Scheduled {currentLeagueObj.name} Matches</span>
            </h2>
            <span className="text-xs font-mono text-gray-400">
              Showing {fixtures.length} of {total} fixtures
            </span>
          </div>

          {loading ? (
            <div className="py-24 text-center">
              <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-xs text-gray-400 font-mono">Fetching latest match schedule...</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center bg-red-500/5 border border-red-500/20 rounded-xl">
              <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
              <p className="text-xs text-red-400">{error}</p>
            </div>
          ) : fixtures.length === 0 ? (
            <div className="p-12 text-center bg-[#0d121f] border border-gray-800 rounded-xl">
              <p className="text-sm text-gray-400">No fixtures found matching current criteria for {currentLeagueObj.name}.</p>
              {valueOnly && (
                <button
                  onClick={() => setValueOnly(false)}
                  className="mt-3 text-xs text-blue-400 hover:underline"
                >
                  Disable value filter to view all scheduled matches
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {fixtures.map((fixture) => (
                <FixtureCard
                  key={fixture.match_id}
                  fixture={fixture}
                  isAnalyst={isAnalyst}
                  onSelect={(id) => setSelectedMatchId(id)}
                  onUpgrade={() => setIsPricingOpen(true)}
                />
              ))}
            </div>
          )}
        </div>
      </>
    )}

        {/* Risk Disclaimer */}
        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800 text-[11px] text-gray-500 leading-relaxed font-mono">
          <strong className="text-gray-400 uppercase">{t("disclaimer.title")}</strong>
          {t("disclaimer.text")}
        </div>
      </main>

      {/* Modals */}
      <AuthModal
        isOpen={isAuthOpen}
        onClose={() => setIsAuthOpen(false)}
        onSuccess={() => {
          fetchUser();
          fetchFixtures();
        }}
      />

      <PricingModal
        isOpen={isPricingOpen}
        onClose={() => setIsPricingOpen(false)}
        user={user}
        onSuccessPayment={() => {
          fetchUser();
          fetchFixtures();
        }}
      />

      <AnalysisModal
        matchId={selectedMatchId}
        fixture={fixtures.find((f) => f.match_id === selectedMatchId)}
        onClose={() => setSelectedMatchId(null)}
      />
    </div>
  );
}

export default function Home() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#080c14] flex items-center justify-center text-gray-500 font-mono text-xs">Loading MatchLambda...</div>}>
      <HomeContent />
    </Suspense>
  );
}
