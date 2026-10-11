export interface LeagueLabel {
  zh: string;
  en: string;
  badge: string;
  short: string;
}

/** Shared bilingual labels. `short` is the compact scanner-filter name. */
export const LEAGUE_LABELS: Record<string, LeagueLabel> = {
  ALL: { zh: "全部", en: "All", badge: "🌐", short: "ALL" },
  TOP5: { zh: "五大联赛", en: "Top 5", badge: "🏆", short: "TOP5" },
  EPL: { zh: "英超", en: "Premier League", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", short: "EPL" },
  LA_LIGA: { zh: "西甲", en: "La Liga", badge: "🇪🇸", short: "La Liga" },
  SERIE_A: { zh: "意甲", en: "Serie A", badge: "🇮🇹", short: "Serie A" },
  BUNDESLIGA: { zh: "德甲", en: "Bundesliga", badge: "🇩🇪", short: "Bundesliga" },
  LIGUE_1: { zh: "法甲", en: "Ligue 1", badge: "🇫🇷", short: "Ligue 1" },
  ALLSVENSKAN: { zh: "瑞超", en: "Allsvenskan", badge: "🇸🇪", short: "Allsvenskan" },
  ELITESERIEN: { zh: "挪超", en: "Eliteserien", badge: "🇳🇴", short: "Eliteserien" },
  SUPERLIGA: { zh: "丹麦超", en: "Superliga", badge: "🇩🇰", short: "Superliga" },
  AUSTRIAN_BUNDESLIGA: { zh: "奥甲", en: "Austrian Bundesliga", badge: "🇦🇹", short: "Austria" },
  CHAMPIONSHIP: { zh: "英冠", en: "Championship", badge: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", short: "Championship" },
  EREDIVISIE: { zh: "荷甲", en: "Eredivisie", badge: "🇳🇱", short: "Eredivisie" },
  PRIMEIRA_LIGA: { zh: "葡超", en: "Primeira Liga", badge: "🇵🇹", short: "Liga Portugal" },
  BEL: { zh: "比甲", en: "Belgian Pro League", badge: "🇧🇪", short: "Pro League" },
  MLS: { zh: "美职联", en: "MLS", badge: "🇺🇸", short: "MLS" },
  BRASILEIRAO: { zh: "巴西甲", en: "Brasileirão", badge: "🇧🇷", short: "Brasileirão" },
  SAUDI_PRO_LEAGUE: { zh: "沙特联", en: "Saudi Pro", badge: "🇸🇦", short: "Saudi Pro" },
  UCL: { zh: "欧冠", en: "Champions League", badge: "⭐", short: "UCL" },
  UEL: { zh: "欧联", en: "Europa League", badge: "🏆", short: "UEL" },
};

export function leagueLabel(id: string, lang: "zh" | "en"): string {
  const row = LEAGUE_LABELS[id];
  if (!row) return id;
  return lang === "en" ? row.en : row.zh;
}

export function leagueShort(id: string): string {
  return LEAGUE_LABELS[id]?.short || id;
}
