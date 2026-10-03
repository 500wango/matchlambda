"use client";

import React, { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Navbar } from "@/components/Navbar";
import { FixtureCard } from "@/components/FixtureCard";
import { AuthModal } from "@/components/AuthModal";
import { PricingModal } from "@/components/PricingModal";
import { AnalysisModal } from "@/components/AnalysisModal";
import { apiRequest, setAuthToken } from "@/lib/api";
import { Shield, Sparkles, Filter, RefreshCw, Calendar, AlertCircle, Trophy } from "lucide-react";

const LEAGUE_CATEGORIES = [
  {
    category: "五大联赛",
    leagues: [
      { id: "EPL", name: "Premier League", country: "England", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
      { id: "LA_LIGA", name: "La Liga", country: "Spain", badge: "🇪🇸" },
      { id: "SERIE_A", name: "Serie A", country: "Italy", badge: "🇮🇹" },
      { id: "BUNDESLIGA", name: "Bundesliga", country: "Germany", badge: "🇩🇪" },
      { id: "LIGUE_1", name: "Ligue 1", country: "France", badge: "🇫🇷" },
    ],
  },
  {
    category: "欧洲杯赛",
    leagues: [
      { id: "UCL", name: "Champions League", country: "Europe", badge: "⭐" },
      { id: "UEL", name: "Europa League", country: "Europe", badge: "🏆" },
    ],
  },
  {
    category: "欧洲主要联赛",
    leagues: [
      { id: "CHAMPIONSHIP", name: "Championship", country: "England", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
      { id: "EREDIVISIE", name: "Eredivisie", country: "Netherlands", badge: "🇳🇱" },
      { id: "PRIMEIRA_LIGA", name: "Primeira Liga", country: "Portugal", badge: "🇵🇹" },
    ],
  },
  {
    category: "美洲及全球",
    leagues: [
      { id: "MLS", name: "MLS", country: "USA", badge: "🇺🇸" },
      { id: "BRASILEIRAO", name: "Brasileirão", country: "Brazil", badge: "🇧🇷" },
      { id: "SAUDI_PRO_LEAGUE", name: "Saudi Pro League", country: "Saudi Arabia", badge: "🇸🇦" },
    ],
  },
];

const ALL_LEAGUES = LEAGUE_CATEGORIES.flatMap((c) => c.leagues);

function HomeContent() {
  const searchParams = useSearchParams();
  const [user, setUser] = useState<any | null>(null);
  const [selectedLeague, setSelectedLeague] = useState<string>("EPL");
  const [activeCategory, setActiveCategory] = useState<string>("五大联赛");
  const [fixtures, setFixtures] = useState<any[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [daysAhead, setDaysAhead] = useState<number>(5);
  const [valueOnly, setValueOnly] = useState<boolean>(false);

  // Modals
  const [isAuthOpen, setIsAuthOpen] = useState<boolean>(false);
  const [isPricingOpen, setIsPricingOpen] = useState<boolean>(false);
  const [selectedMatchId, setSelectedMatchId] = useState<string | null>(null);

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
      let query = `/matches/fixtures?league_id=${selectedLeague}&days_ahead=${daysAhead}&limit=50&offset=0`;
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

  const isAnalyst = user?.effective_plan === "ANALYST";
  const currentLeagueObj = ALL_LEAGUES.find((l) => l.id === selectedLeague) || ALL_LEAGUES[0];

  return (
    <div className="min-h-screen flex flex-col bg-[#080c14] text-gray-100">
      <Navbar
        user={user}
        onOpenAuth={() => setIsAuthOpen(true)}
        onOpenPricing={() => setIsPricingOpen(true)}
        onLogout={handleLogout}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* League Selector Group */}
        <div className="space-y-3 pb-3 border-b border-gray-800/80">
          {/* Category Tabs */}
          <div className="flex items-center space-x-2 overflow-x-auto pb-1 scrollbar-none">
            {LEAGUE_CATEGORIES.map((cat) => {
              const isCatActive = cat.category === activeCategory;
              return (
                <button
                  key={cat.category}
                  onClick={() => {
                    setActiveCategory(cat.category);
                    setSelectedLeague(cat.leagues[0].id);
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
            {(LEAGUE_CATEGORIES.find((c) => c.category === activeCategory)?.leagues || ALL_LEAGUES).map((league) => {
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
              {[1, 3, 5, 7].map((days) => (
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

        {/* Risk Disclaimer */}
        <div className="p-4 rounded-xl bg-gray-900/40 border border-gray-800 text-[11px] text-gray-500 leading-relaxed font-mono">
          <strong className="text-gray-400 uppercase">Analytical Disclaimer: </strong>
          MatchLambda estimates are generated via regulation-time Dixon–Coles Poisson modeling.
          Market-derived probabilities and Shin de-juiced odds are statistical approximations, not
          ground truth. A positive unrounded EV (≥ 0.05) or Half-Kelly fraction does not constitute
          financial advice, trade execution, or any guarantee of profitability.
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

      <AnalysisModal matchId={selectedMatchId} onClose={() => setSelectedMatchId(null)} />
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
