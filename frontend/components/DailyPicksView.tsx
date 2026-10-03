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

interface DailyPicksViewProps {
  isAnalyst: boolean;
  onOpenPricing: () => void;
  onSelectMatch: (matchId: string) => void;
}

const LEAGUE_LABELS: Record<string, { name: string; badge: string }> = {
  EPL: { name: "英超", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  LA_LIGA: { name: "西甲", badge: "🇪🇸" },
  SERIE_A: { name: "意甲", badge: "🇮🇹" },
  BUNDESLIGA: { name: "德甲", badge: "🇩🇪" },
  LIGUE_1: { name: "法甲", badge: "🇫🇷" },
  ALLSVENSKAN: { name: "瑞超", badge: "🇸🇪" },
  ELITESERIEN: { name: "挪超", badge: "🇳🇴" },
  SUPERLIGA: { name: "丹麦超", badge: "🇩🇰" },
  AUSTRIAN_BUNDESLIGA: { name: "奥甲", badge: "🇦🇹" },
  CHAMPIONSHIP: { name: "英冠", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  EREDIVISIE: { name: "荷甲", badge: "🇳🇱" },
  PRIMEIRA_LIGA: { name: "葡超", badge: "🇵🇹" },
  MLS: { name: "美职联", badge: "🇺🇸" },
  BRASILEIRAO: { name: "巴西甲", badge: "🇧🇷" },
  SAUDI_PRO_LEAGUE: { name: "沙特联", badge: "🇸🇦" },
  UCL: { name: "欧冠", badge: "⭐" },
  UEL: { name: "欧联", badge: "🏆" },
};

export const DailyPicksView: React.FC<DailyPicksViewProps> = ({
  isAnalyst,
  onOpenPricing,
  onSelectMatch,
}) => {
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
      let query = "/picks/daily?days_ahead=10";
      if (selectedLeague && selectedLeague !== "ALL") {
        query += `&league_id=${selectedLeague}`;
      }
      const res = await apiRequest<any>(query);
      setData(res);
    } catch (err: any) {
      setError(err?.message || "获取智能推荐失败，请重试。");
    } finally {
      setLoading(false);
    }
  }, [selectedLeague]);

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

  // Compile list of matches based on category
  const getFilteredPicks = () => {
    if (!data) return [];
    if (selectedCategory === "BANKER") return data.bankers || [];
    if (selectedCategory === "VALUE") return data.values || [];
    if (selectedCategory === "UNDERDOG") return data.underdogs || [];
    if (selectedCategory === "GOALS") return data.goals || [];
    if (selectedCategory === "PARLAYS") return [];

    // "ALL": Merge with clear priority
    const allList = [
      ...(data.bankers || []),
      ...(data.values || []),
      ...(data.goals || []),
      ...(data.underdogs || []),
    ];
    // Deduplicate by pick_id
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
              <span>专为普通与进阶玩家设计 · AI 每日智能精选</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              告别繁琐公式与希腊字母，直接看懂每一场胜负逻辑
            </h2>
            <p className="text-sm text-gray-300 leading-relaxed">
              基于两千场五大联赛与全球顶级赛事回测调优的 Dixon-Coles 双变量泊松模型，自动扫描出{" "}
              <strong className="text-emerald-400">今日高胜率稳胆</strong>、
              <strong className="text-blue-400">机构低估黄金单</strong> 与{" "}
              <strong className="text-purple-400">一键智能 2 串 1 方案</strong>
              。不用懂量化数学，也能尊享机构级超额收益优势。
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            <button
              onClick={fetchPicks}
              disabled={loading}
              className="w-full sm:w-auto inline-flex items-center justify-center space-x-2 px-4 py-2.5 rounded-xl bg-gray-900/80 hover:bg-gray-800 border border-gray-700 text-xs font-bold text-gray-200 transition"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin text-emerald-400" : ""}`} />
              <span>刷新推荐池</span>
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
            <span>🌟 全部精选</span>
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
            <span>🔗 智能串关方案 (2串1 / 3串1)</span>
            <span className="text-[10px] bg-blue-500/20 text-blue-300 px-1.5 py-0.5 rounded-full font-mono">
              3套
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
            <span>⭐ 今日稳胆 (胜率 60%+)</span>
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
            <span>🔥 每日强推 (+EV 性价比)</span>
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
            <span>⚽ 进球狂欢 (大球/双进)</span>
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
            <span>💣 搏冷高赔 (3.0+ 高倍)</span>
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
            <span>联赛范围:</span>
          </span>
          {[
            { id: "ALL", name: "全部赛事" },
            { id: "TOP5", name: "五大联赛" },
            { id: "EPL", name: "英超" },
            { id: "LA_LIGA", name: "西甲" },
            { id: "SERIE_A", name: "意甲" },
            { id: "BUNDESLIGA", name: "德甲" },
            { id: "LIGUE_1", name: "法甲" },
            { id: "CUPS", name: "欧战杯赛" },
            { id: "NORDIC", name: "北欧与中欧" },
          ].map((l) => (
            <button
              key={l.id}
              onClick={() => setSelectedLeague(l.id)}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
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
          <p className="text-gray-400 text-sm">正在深度计算全量赛程泊松期望与智能推荐方案...</p>
        </div>
      )}

      {error && (
        <div className="p-6 bg-red-950/20 border border-red-500/30 rounded-2xl text-center space-y-3">
          <p className="text-red-400 font-bold">{error}</p>
          <button
            onClick={fetchPicks}
            className="px-4 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-300 text-xs font-bold rounded-lg transition"
          >
            点击重试
          </button>
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Section 1: Smart Parlays Showcase (Shows when ALL or PARLAYS is selected) */}
          {(selectedCategory === "ALL" || selectedCategory === "PARLAYS") &&
            data?.parlays &&
            data.parlays.length > 0 && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <TrendingUp className="w-5 h-5 text-blue-400" />
                    <h3 className="text-lg font-extrabold text-white">
                      智能串关组合票 (1-Click Smart Parlays)
                    </h3>
                  </div>
                  <span className="text-xs text-gray-400">
                    科学搭配 · 自动优化盈亏比与独立事件概率
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
                            预估胜率: <strong className="text-white">{parlay.win_probability_pct}%</strong>
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
                              <span className="text-xs text-gray-400 block">组合总赔率</span>
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
                                投 {parlay.suggested_unit} 元预计奖金
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
                            包含场次 ({parlay.legs.length} 场):
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
                                    推荐: <span className="text-emerald-300 font-bold">{leg.selection}</span>
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
                                <span>已复制方案到剪贴板！</span>
                              </>
                            ) : (
                              <>
                                <Copy className="w-4 h-4" />
                                <span>一键复制推荐方案 (发朋友/微信)</span>
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
                    {selectedCategory === "BANKER"
                      ? "⭐ 今日稳胆精选 (高确定性强胆)"
                      : selectedCategory === "VALUE"
                      ? "🔥 每日超额价值强推 (机构失真肉签)"
                      : selectedCategory === "GOALS"
                      ? "⚽ 进球狂欢 (大球与对攻大战)"
                      : selectedCategory === "UNDERDOG"
                      ? "💣 搏冷高赔精选 (高赔小博大)"
                      : "🌟 今日精选单场赛事推荐"}
                  </h3>
                </div>
                <span className="text-xs text-gray-400">
                  共计 <strong>{filteredPicks.length}</strong> 场深度解析
                </span>
              </div>

              {filteredPicks.length === 0 ? (
                <div className="p-12 text-center bg-[#111726] border border-gray-800 rounded-2xl space-y-2">
                  <p className="text-gray-400 text-sm">当前联赛分类下暂无符合苛刻门槛的推荐。</p>
                  <button
                    onClick={() => {
                      setSelectedLeague("ALL");
                      setSelectedCategory("ALL");
                    }}
                    className="text-xs text-blue-400 font-bold hover:underline"
                  >
                    查看全网所有联赛推荐
                  </button>
                </div>
              ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {filteredPicks.map((pick: any) => {
                    const leagueBadge = LEAGUE_LABELS[pick.league_id]?.badge || "⚽";
                    const leagueName = LEAGUE_LABELS[pick.league_id]?.name || pick.league_id;
                    const matchDate = new Date(pick.match_date);
                    const dateFormatted = matchDate.toLocaleDateString(undefined, {
                      month: "numeric",
                      day: "numeric",
                      weekday: "short",
                    });
                    const timeFormatted = matchDate.toLocaleTimeString(undefined, {
                      hour: "2-digit",
                      minute: "2-digit",
                    });

                    const isBanker = pick.category === "BANKER";
                    const isValue = pick.category === "VALUE";
                    const isUnderdog = pick.category === "UNDERDOG";
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
                              预期进球 xG: {pick.expected_goals?.home || 1.0}
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
                              预期进球 xG: {pick.expected_goals?.away || 1.0}
                            </span>
                          </div>
                        </div>

                        {/* Recommendation Highlight Box */}
                        <div className="p-4 rounded-xl bg-gradient-to-r from-gray-900/90 to-gray-950 border border-gray-800/80 flex items-center justify-between">
                          <div>
                            <span className="text-[11px] text-gray-400 block mb-0.5">
                              推荐方案 / 盘口
                            </span>
                            <div className="flex items-center space-x-2">
                              <span className="text-base font-extrabold text-white">
                                {pick.selection_name}
                              </span>
                              <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-mono font-bold text-xs">
                                赔率 @{pick.market_odds.toFixed(2)}
                              </span>
                            </div>
                          </div>

                          <div className="text-right">
                            <span className="text-[11px] text-gray-400 block mb-0.5">
                              模型概率 / 理论赔率
                            </span>
                            <div className="font-mono text-xs">
                              <span className="font-bold text-emerald-400">
                                {roundPct(pick.model_probability)}%
                              </span>
                              <span className="text-gray-500 ml-1">
                                (公正: {pick.fair_odds.toFixed(2)})
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Top Predicted Exact Scores */}
                        {pick.top_scores && pick.top_scores.length > 0 && (
                          <div className="flex items-center justify-between text-xs py-2 px-3 rounded-lg bg-gray-900/40 border border-gray-800/60 font-mono">
                            <span className="text-gray-400 text-[11px]">预测最可能比分:</span>
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
                            <span>AI 核心拆解理由</span>
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
                            <span>完整 6x6 矩阵</span>
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
