"use client";

import React from "react";
import { Clock, TrendingUp, Shield, ChevronRight, AlertCircle } from "lucide-react";
import { useI18n } from "@/lib/i18n";

interface FixtureCardProps {
  fixture: any;
  isAnalyst: boolean;
  onSelect: (matchId: string) => void;
  onUpgrade: () => void;
}

const LEAGUE_LABELS: Record<string, { zh: string; en: string; badge: string }> = {
  EPL: { zh: "英超 Premier League", en: "Premier League", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  LA_LIGA: { zh: "西甲 La Liga", en: "La Liga", badge: "🇪🇸" },
  SERIE_A: { zh: "意甲 Serie A", en: "Serie A", badge: "🇮🇹" },
  BUNDESLIGA: { zh: "德甲 Bundesliga", en: "Bundesliga", badge: "🇩🇪" },
  LIGUE_1: { zh: "法甲 Ligue 1", en: "Ligue 1", badge: "🇫🇷" },
  ALLSVENSKAN: { zh: "瑞超 Allsvenskan", en: "Allsvenskan", badge: "🇸🇪" },
  ELITESERIEN: { zh: "挪超 Eliteserien", en: "Eliteserien", badge: "🇳🇴" },
  SUPERLIGA: { zh: "丹麦超 Superliga", en: "Superliga", badge: "🇩🇰" },
  AUSTRIAN_BUNDESLIGA: { zh: "奥甲/奥超 Bundesliga", en: "Austrian Bundesliga", badge: "🇦🇹" },
  CHAMPIONSHIP: { zh: "英冠 Championship", en: "Championship", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿" },
  EREDIVISIE: { zh: "荷甲 Eredivisie", en: "Eredivisie", badge: "🇳🇱" },
  PRIMEIRA_LIGA: { zh: "葡超 Primeira Liga", en: "Primeira Liga", badge: "🇵🇹" },
  MLS: { zh: "美职联 MLS", en: "MLS", badge: "🇺🇸" },
  BRASILEIRAO: { zh: "巴西甲 Brasileirão", en: "Brasileirão", badge: "🇧🇷" },
  SAUDI_PRO_LEAGUE: { zh: "沙特联 Saudi Pro", en: "Saudi Pro", badge: "🇸🇦" },
  UCL: { zh: "欧冠 Champions League", en: "Champions League", badge: "⭐" },
  UEL: { zh: "欧联 Europa League", en: "Europa League", badge: "🏆" },
};

export const FixtureCard: React.FC<FixtureCardProps> = ({
  fixture,
  isAnalyst,
  onSelect,
  onUpgrade,
}) => {
  const { lang } = useI18n();
  const isEn = lang === "en";

  const matchDate = new Date(fixture.match_date);
  const formattedDate = matchDate.toLocaleDateString(isEn ? "en-US" : "zh-CN", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
  const formattedTime = matchDate.toLocaleTimeString(isEn ? "en-US" : "zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const pred = fixture.prediction;
  const comp = fixture.comparison;
  const hasValue = comp?.has_value;
  const leagueObj = LEAGUE_LABELS[fixture.league_id];
  const leagueName = isEn ? (leagueObj?.en || fixture.league_id) : (leagueObj?.zh || fixture.league_id);
  const leagueBadge = leagueObj?.badge || "⚽";

  return (
    <div className="bg-[#111726] border border-gray-800/80 hover:border-gray-700 rounded-xl p-5 transition shadow-lg relative group">
      {/* Top row: league & date */}
      <div className="flex items-center justify-between text-xs text-gray-400 mb-4 pb-3 border-b border-gray-800/60 font-mono">
        <span className="inline-flex items-center space-x-1.5 font-bold text-blue-400 uppercase tracking-wider">
          <span>{leagueBadge}</span>
          <span>{leagueName}</span>
        </span>
        <div className="flex items-center space-x-1.5" suppressHydrationWarning>
          <Clock className="w-3.5 h-3.5 text-gray-500" />
          <span suppressHydrationWarning>
            {formattedDate} · {formattedTime}
          </span>
        </div>
      </div>

      {/* Teams */}
      <div className="flex items-center justify-between mb-5">
        <div className="w-5/12 text-left">
          <h4 className="font-bold text-white text-base truncate">{fixture.home_team.name}</h4>
          <span className="text-[11px] text-gray-500 font-mono">{isEn ? "HOME" : "主场"}</span>
        </div>

        <div className="w-2/12 text-center text-xs font-mono font-bold text-gray-500 bg-gray-900/60 py-1 rounded">
          VS
        </div>

        <div className="w-5/12 text-right">
          <h4 className="font-bold text-white text-base truncate">{fixture.away_team.name}</h4>
          <span className="text-[11px] text-gray-500 font-mono">{isEn ? "AWAY" : "客场"}</span>
        </div>
      </div>

      {/* Analyst probability preview or free locked teaser */}
      {isAnalyst ? (
        pred && comp ? (
          <div className="space-y-3 pt-2">
            {/* Probability Bars */}
            <div className="flex items-center justify-between text-xs font-mono text-gray-300">
              <span className="text-blue-400 font-bold">{(pred.prob_home_win * 100).toFixed(1)}%</span>
              <span className="text-gray-400">{(pred.prob_draw * 100).toFixed(1)}%</span>
              <span className="text-indigo-400 font-bold">{(pred.prob_away_win * 100).toFixed(1)}%</span>
            </div>

            <div className="h-2 w-full bg-gray-900 rounded-full flex overflow-hidden">
              <div
                style={{ width: `${pred.prob_home_win * 100}%` }}
                className="bg-blue-500"
                title={`Home Win: ${(pred.prob_home_win * 100).toFixed(1)}%`}
              />
              <div
                style={{ width: `${pred.prob_draw * 100}%` }}
                className="bg-gray-600"
                title={`Draw: ${(pred.prob_draw * 100).toFixed(1)}%`}
              />
              <div
                style={{ width: `${pred.prob_away_win * 100}%` }}
                className="bg-indigo-500"
                title={`Away Win: ${(pred.prob_away_win * 100).toFixed(1)}%`}
              />
            </div>

            {/* Odds & Value signal */}
            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center space-x-2">
                {hasValue ? (
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    <TrendingUp className="w-3 h-3 mr-1" /> {isEn ? "VALUE SIGNAL" : "价值机会"}
                  </span>
                ) : (
                  <span className="text-[11px] font-mono text-gray-500">{isEn ? "Fairly Priced" : "价格合理"}</span>
                )}
              </div>

              <button
                onClick={() => onSelect(fixture.match_id)}
                className="inline-flex items-center text-xs font-semibold text-blue-400 hover:text-blue-300 transition"
              >
                {isEn ? "Deep Analysis" : "深度分析"} <ChevronRight className="w-4 h-4 ml-0.5" />
              </button>
            </div>
          </div>
        ) : (
          <div className="py-3 px-3 bg-gray-900/50 rounded-lg text-center font-mono text-xs text-gray-500">
            {fixture.reason || (isEn ? "Prediction unavailable for this fixture." : "本场暂无预测数据。")}
          </div>
        )
      ) : (
        <div className="mt-3 p-3 bg-[#0a0f1d] border border-gray-800 rounded-lg flex items-center justify-between">
          <div className="flex items-center space-x-2 text-xs text-gray-400">
            <Shield className="w-4 h-4 text-blue-400 flex-shrink-0" />
            <span>{isEn ? "Probabilities & EV hidden" : "概率与 EV 权限已隐藏"}</span>
          </div>
          <button
            onClick={onUpgrade}
            className="text-xs font-semibold text-blue-400 hover:text-blue-300 hover:underline"
          >
            {isEn ? "Unlock Pass" : "解锁专家权限"}
          </button>
        </div>
      )}
    </div>
  );
};
