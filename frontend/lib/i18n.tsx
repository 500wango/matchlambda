"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";

export type Language = "zh" | "en";

export interface I18nContextType {
  lang: Language;
  setLang: (lang: Language) => void;
  toggleLang: () => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}

const translations: Record<Language, Record<string, any>> = {
  zh: {
    nav: {
      brand: "MatchLambda",
      version: "v1.3.0",
      subtitle: "双变量泊松分布与全球顶级赛事量化终端",
      login: "登录",
      logout: "退出登录",
      getPass: "开通 Analyst 权限",
      upgrade: "升级权限",
      langSwitch: "English",
      free: "免费版",
      analyst: "ANALYST 专家",
    },
    tabs: {
      picks: "🎯 今日智能推荐 (Daily Picks)",
      scanner: "⚡ +EV 价值雷达 (Alpha Scanner)",
      fixtures: "⚽ 赛程与多盘口预测 (Match Feeds)",
      backtest: "📈 量化回测与资金曲线 (Track Record)",
      simulator: "💼 蒙特卡洛情景模拟 (Monte Carlo)",
      liveTicker: "最新有效 +EV 信号:",
      odds: "赔率",
    },
    picks: {
      bannerBadge: "有效赛前数据 · 模型概率估计",
      bannerTitle: "查看赛前概率估计与已记录赔率",
      bannerDesc:
        "推荐列表使用当前有效的预测和赔率快照。大小球与双方进球展示模型估计；没有对应的机构赔率时不会计算 EV。",
      refreshBtn: "刷新推荐池",
      all: "🌟 全部精选",
      parlays: "🔗 智能串关方案 (2串1 / 3串1)",
      banker: "⭐ 模型高概率结果",
      value: "🔥 每日强推 (+EV 性价比)",
      goals: "⚽ 进球狂欢 (大球/双进)",
      underdog: "💣 搏冷高赔 (3.0+ 高倍)",
      leagueScope: "联赛范围:",
      loading: "正在深度计算全量赛程泊松期望与智能推荐方案...",
      parlayTitle: "智能串关组合票 (1-Click Smart Parlays)",
      parlaySubtitle: "组合概率按各场估计相乘，并假设比赛结果相互独立",
      estWinRate: "预估胜率:",
      combOdds: "组合总赔率",
      stakeReturn: "投 {unit} 元预计奖金",
      includedLegs: "包含场次",
      recLabel: "推荐:",
      copyBtn: "一键复制推荐方案 (发朋友/微信)",
      copied: "已复制方案到剪贴板！",
      singleSectionTitle: "🌟 今日精选单场赛事推荐",
      totalAnalyses: "共计 {count} 场深度解析",
      noPicks: "当前联赛分类下暂无符合苛刻门槛的推荐。",
      viewAllLeagues: "查看全网所有联赛推荐",
      home: "HOME",
      away: "AWAY",
      expectedGoals: "预期进球 xG:",
      recMarket: "推荐方案 / 盘口",
      modelVsFair: "模型概率 / 理论赔率",
      fair: "公正:",
      topScores: "预测最可能比分:",
      aiRationale: "AI 核心拆解理由",
      matrixBtn: "完整 6x6 矩阵",
      starUnit: "场",
      setsUnit: "套",
    },
    leagues: {
      all: "全部赛事",
      top5: "五大联赛",
      epl: "英超",
      laLiga: "西甲",
      serieA: "意甲",
      bundesliga: "德甲",
      ligue1: "法甲",
      cups: "欧战杯赛",
      nordic: "北欧与中欧",
      euroOther: "欧洲其他主要联赛",
      global: "美洲及全球联赛",
    },
    scanner: {
      title: "量化价值雷达 (+EV Scanner)",
      subtitle: "将通过时效校验的赛前 1X2 赔率与模型概率估计进行比较。",
      signalsFound: "捕获 {count} 个正期望机会",
      minEv: "最低期望值 (Min EV):",
      bankroll: "模拟本金:",
      strategy: "资金策略:",
      match: "赛事对阵",
      league: "联赛",
      market: "盘口类型",
      selection: "推荐选项",
      bookmaker: "机构",
      marketOdds: "市场赔率",
      fairOdds: "理论公允",
      edge: "数学优势 (Edge)",
      ev: "期望收益 (EV)",
      suggestedStake: "建议下注",
      expectedProfit: "预期利润",
      grade: "评级",
      action: "深度分析",
      noSignals: "暂无符合当前过滤门槛的 +EV 信号。",
    },
    backtest: {
      title: "历史实盘回测与业绩曲线",
      subtitle: "使用已保存的赛前预测、有效赔率快照、完赛结果和可用的终盘赔率。",
      initialCapital: "初始资金",
      totalReturn: "总收益率 (ROI)",
      winRate: "真实胜率",
      maxDd: "最大回撤",
      sharpe: "夏普比率",
      beatClv: "击败收盘线率",
      totalTrades: "总交易场次",
      profit: "总净利润",
      equityCurve: "资金增长净值曲线 (Equity Curve)",
      recentTrades: "近期实盘交易审计流水",
    },
    simulator: {
      title: "蒙特卡洛多路径破产风险模拟器",
      subtitle: "根据输入的平均 EV、赔率和凯利比例构造假设的独立投注路径，不代表历史模型表现。",
      simulateBtn: "重新执行 1,000 次模拟",
      expectedMedian: "预期中位数资金",
      medianGrowth: "中位资金增长率",
      doubleProb: "资金翻倍概率",
      ruinRisk: "资金跌至初始值 20% 以下的概率",
      worstCase: "最差 5% 极端下行 (VaR)",
      bestCase: "最优 5% 爆发收益",
      paths: "蒙特卡洛模拟轨迹 (前 8 条代表路径)",
    },
    modal: {
      close: "关闭",
      depthAnalysis: "赛事深度量化分析",
      matrix: "6x6 比分概率矩阵",
      kellyCalc: "凯利资金计算器",
      analystExclusive: "此功能为 ANALYST 专家专享",
      unlock: "立即升级解锁",
      tabs: {
        matchOdds: "1X2 独赢盘",
        totals: "大小球 (Totals)",
        btts: "双方皆进球 (BTTS)",
        handicap: "亚洲让球盘",
        doubleChance: "双重机会 & DNB",
        matrix: "6x6 比分概率矩阵",
        kelly: "凯利资金计算器",
      },
    },
    auth: {
      loginTitle: "登录 MatchLambda",
      registerTitle: "创建 MatchLambda 账号",
      email: "邮箱地址",
      password: "密码",
      needAccount: "还没有账号？点击免费注册",
      hasAccount: "已有账号？点击登录",
      loginSubmit: "立即登录",
      registerSubmit: "注册并开始使用",
    },
    pricing: {
      title: "升级 ANALYST 专家会员",
      subtitle: "解锁时效校验后的 +EV 信号、比分概率矩阵与模型衍生市场估计。",
      payCrypto: "使用加密货币支付",
      monthly: "30天通行证",
      quarterly: "270天赛季通行证",
      instantActivation: "支付确认后自动开通",
    },
    disclaimer: {
      title: "免责声明: ",
      text: "MatchLambda 提供的概率预测基于常规时间（90分钟）Dixon-Coles 泊松分布模型。机构去水概率与正期望值（EV）属于统计学估算，不构成任何形式的财务建议、实盘下注邀请或确定性收益保证。请理性参与。",
    },
  },
  en: {
    nav: {
      brand: "MatchLambda",
      version: "v1.3.0",
      subtitle: "Bivariate Poisson Model & Global Football Quant Terminal",
      login: "Log in",
      logout: "Log out",
      getPass: "Get Analyst Pass",
      upgrade: "Upgrade Pass",
      langSwitch: "中文",
      free: "FREE",
      analyst: "ANALYST PRO",
    },
    tabs: {
      picks: "🎯 Daily AI Picks & Parlays",
      scanner: "⚡ +EV Alpha Scanner",
      fixtures: "⚽ Match Feeds & Markets",
      backtest: "📈 Track Record & Backtest",
      simulator: "💼 Monte Carlo Scenarios",
      liveTicker: "Latest eligible +EV signals:",
      odds: "Odds",
    },
    picks: {
      bannerBadge: "Eligible pre-match data · Model estimates",
      bannerTitle: "View model probability estimates and stored odds",
      bannerDesc:
        "Daily picks use current eligible predictions and stored odds snapshots. Totals and BTTS show model estimates; EV is omitted when the matching bookmaker price is unavailable.",
      refreshBtn: "Refresh Picks",
      all: "🌟 All Featured",
      parlays: "🔗 Smart Parlays (2-Fold / 3-Fold)",
      banker: "⭐ Higher Model Probability",
      value: "🔥 Best Value (+EV Edge)",
      goals: "⚽ Goal Feast (Over 2.5 / BTTS)",
      underdog: "💣 Value Underdogs (3.0+ Odds)",
      leagueScope: "League Filter:",
      loading: "Computing Dixon-Coles Poisson expectations & smart parlays...",
      parlayTitle: "1-Click Smart Parlay Tickets",
      parlaySubtitle: "Combined probability multiplies individual estimates and assumes independent fixtures",
      estWinRate: "Est. Win Rate:",
      combOdds: "Combined Odds",
      stakeReturn: "Stake ¥{unit} -> Est. Payout",
      includedLegs: "Included Matches",
      recLabel: "Pick:",
      copyBtn: "1-Click Copy Ticket Summary",
      copied: "Copied to Clipboard!",
      singleSectionTitle: "🌟 Curated Match Picks & Previews",
      totalAnalyses: "{count} matches analyzed",
      noPicks: "No matches meet the threshold under this filter.",
      viewAllLeagues: "View All Leagues",
      home: "HOME",
      away: "AWAY",
      expectedGoals: "Projected xG:",
      recMarket: "Recommended Selection / Market",
      modelVsFair: "Model Prob / Fair Odds",
      fair: "Fair:",
      topScores: "Most Likely Scores:",
      aiRationale: "AI Model Rationale",
      matrixBtn: "Full 6x6 Matrix",
      starUnit: "matches",
      setsUnit: "sets",
    },
    leagues: {
      all: "All Leagues",
      top5: "Top 5 European",
      epl: "Premier League",
      laLiga: "La Liga",
      serieA: "Serie A",
      bundesliga: "Bundesliga",
      ligue1: "Ligue 1",
      cups: "European Cups",
      nordic: "Nordic & Central Europe",
      euroOther: "Other European Leagues",
      global: "Americas & Global",
    },
    scanner: {
      title: "Quantitative +EV Alpha Scanner",
      subtitle: "Compares eligible pre-kickoff 1X2 quotes with stored model probability estimates.",
      signalsFound: "{count} positive EV opportunities found",
      minEv: "Min EV Threshold:",
      bankroll: "Simulated Bankroll:",
      strategy: "Staking Strategy:",
      match: "Fixture",
      league: "League",
      market: "Market Type",
      selection: "Selection",
      bookmaker: "Bookmaker",
      marketOdds: "Market Odds",
      fairOdds: "Fair Odds",
      edge: "Edge (%)",
      ev: "EV (%)",
      suggestedStake: "Suggested Stake",
      expectedProfit: "Exp. Profit",
      grade: "Grade",
      action: "Quant Dive",
      noSignals: "No +EV signals matching current filter criteria.",
    },
    backtest: {
      title: "Historical Model Backtest",
      subtitle: "Uses stored pre-kickoff predictions, eligible odds snapshots, completed results, and available closing quotes.",
      initialCapital: "Initial Capital",
      totalReturn: "Total ROI",
      winRate: "Win Rate",
      maxDd: "Max Drawdown",
      sharpe: "Sharpe Ratio",
      beatClv: "Beat CLV Rate",
      totalTrades: "Total Bets",
      profit: "Net Profit",
      equityCurve: "Portfolio Equity Growth Curve",
      recentTrades: "Sample Trade Audit Log",
    },
    simulator: {
      title: "Monte Carlo Portfolio & Ruin Risk Simulator",
      subtitle: "Hypothetical independent-bet scenarios based only on the average EV, odds, and stake assumptions entered below.",
      simulateBtn: "Run 1,000 Simulations",
      expectedMedian: "Median Bankroll",
      medianGrowth: "Median Growth",
      doubleProb: "Doubling Probability",
      ruinRisk: "Chance of falling below 20% of start",
      worstCase: "Worst 5% Tail Risk (VaR)",
      bestCase: "Best 5% Upside Path",
      paths: "Sample Monte Carlo Trajectories (Top 8 Paths)",
    },
    modal: {
      close: "Close",
      depthAnalysis: "Match Quantitative Deep Dive",
      matrix: "6x6 Score Probability Matrix",
      kellyCalc: "Kelly Staking Calculator",
      analystExclusive: "ANALYST Pro Access Only",
      unlock: "Unlock Pro Access",
      tabs: {
        matchOdds: "1X2 Regulation",
        totals: "Totals (Over/Under)",
        btts: "Both Teams To Score",
        handicap: "Asian Handicap",
        doubleChance: "Double Chance & DNB",
        matrix: "6x6 Score Matrix",
        kelly: "Kelly Calculator",
      },
    },
    auth: {
      loginTitle: "Log in to MatchLambda",
      registerTitle: "Create MatchLambda Account",
      email: "Email Address",
      password: "Password",
      needAccount: "Don't have an account? Sign up free",
      hasAccount: "Already have an account? Sign in",
      loginSubmit: "Sign In",
      registerSubmit: "Register & Start",
    },
    pricing: {
      title: "Upgrade to ANALYST Pro",
      subtitle: "Unlock freshness-checked +EV signals, score probability matrices, and model-derived market estimates.",
      payCrypto: "Pay with Cryptocurrency",
      monthly: "30-Day Pass",
      quarterly: "270-Day Season Pass",
      instantActivation: "Activated after payment confirmation",
    },
    disclaimer: {
      title: "Analytical Disclaimer: ",
      text: "MatchLambda estimates are generated via regulation-time Dixon–Coles Poisson modeling. Market-derived probabilities and Shin de-juiced odds are statistical approximations, not financial advice, trade execution, or any guarantee of profitability. Please wager responsibly.",
    },
  },
};

const I18nContext = createContext<I18nContextType>({
  lang: "zh",
  setLang: () => {},
  toggleLang: () => {},
  t: (key: string) => key,
});

export const I18nProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Language>("zh");

  useEffect(() => {
    try {
      const savedLang = localStorage.getItem("matchlambda_lang");
      if (savedLang === "zh" || savedLang === "en") {
        setLangState(savedLang);
      } else if (navigator.language && navigator.language.toLowerCase().startsWith("en")) {
        setLangState("en");
      }
    } catch {
      // Ignore SSR / localStorage issues
    }
  }, []);

  const setLang = (newLang: Language) => {
    setLangState(newLang);
    try {
      localStorage.setItem("matchlambda_lang", newLang);
    } catch {
      // Ignore
    }
  };

  const toggleLang = () => {
    setLang(lang === "zh" ? "en" : "zh");
  };

  const t = (key: string, params?: Record<string, string | number>): string => {
    const keys = key.split(".");
    let current: any = translations[lang];

    for (const k of keys) {
      if (current && typeof current === "object" && k in current) {
        current = current[k];
      } else {
        // Fallback to English if missing in Chinese
        let fallback: any = translations.en;
        for (const fbKey of keys) {
          if (fallback && typeof fallback === "object" && fbKey in fallback) {
            fallback = fallback[fbKey];
          } else {
            return key;
          }
        }
        current = fallback;
        break;
      }
    }

    if (typeof current !== "string") {
      return key;
    }

    if (params) {
      return Object.entries(params).reduce((acc, [paramKey, paramVal]) => {
        return acc.replace(new RegExp(`\\{${paramKey}\\}`, "g"), String(paramVal));
      }, current);
    }

    return current;
  };

  return (
    <I18nContext.Provider value={{ lang, setLang, toggleLang, t }}>
      {children}
    </I18nContext.Provider>
  );
};

export const useI18n = (): I18nContextType => {
  return useContext(I18nContext);
};
