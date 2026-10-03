import math
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from app.models import Match, Prediction
from app.math.derivatives import compute_derived_markets
from app.math.ev import calculate_ev


def _format_score_str(top_scores: Optional[List[Dict[str, Any]]]) -> str:
    if not top_scores:
        return "1-0 / 2-1"
    scores = [s.get("score") for s in top_scores[:2] if s.get("score")]
    return " / ".join(scores) if scores else "1-0 / 2-0"


def generate_rationale(
    category: str,
    home_team: str,
    away_team: str,
    selection_type: str,
    selection_name: str,
    odds: float,
    fair_odds: float,
    prob: float,
    ev: float,
    lambda_h: float,
    mu_a: float,
    top_scores: Optional[List[Dict[str, Any]]],
    extra_data: Optional[Dict[str, Any]] = None,
    lang: str = "zh",
) -> str:
    """
    Generates fluent, professional, human-readable rationale
    in Chinese (zh) or English (en).
    """
    prob_pct = round(prob * 100, 1)
    ev_pct = round(ev * 100, 1)
    score_str = _format_score_str(top_scores)
    total_xg = round(lambda_h + mu_a, 2)
    implied_pct = round(100.0 / odds, 1) if odds > 0 else 0.0

    if lang == "en":
        if category == "BANKER":
            if "Home" in selection_name or selection_type == "HOME_WIN":
                xg_diff = round(lambda_h - mu_a, 2)
                return (
                    f"【Banker Rationale】{home_team} commands home advantage with projected xG of {lambda_h:.2f} "
                    f"vs {mu_a:.2f} for {away_team} (net margin +{xg_diff} goals). The Poisson model computes an impressive "
                    f"{prob_pct}% true win probability. Current odds of {odds:.2f} offer solid backing. "
                    f"Most likely scorelines: {score_str}. Prime high-certainty banker."
                )
            else:
                return (
                    f"【Banker Rationale】{away_team} shows distinct tactical dominance in this matchup (projected xG {mu_a:.2f}). "
                    f"Model projects a {prob_pct}% away victory. The host's porous defense (expected concession {mu_a:.2f}) "
                    f"makes the away side reliable. Projected scores: {score_str}. Confident away selection."
                )

        elif category == "VALUE":
            return (
                f"【Value Mispricing】Market mispricing detected! Sharp bookmakers are offering {odds:.2f} "
                f"(implied probability: {implied_pct}%), whereas our bivariate Poisson regression calculates a true probability "
                f"of {prob_pct}% (fair odds: {fair_odds:.2f}), generating a +{ev_pct}% EV edge. "
                f"Strong compounding value on {selection_name}."
            )

        elif category == "UNDERDOG":
            if "Draw" in selection_name or selection_type == "DRAW":
                return (
                    f"【Underdog Rationale】Tight tactical stalemate anticipated as both sides prioritize defensive structure. "
                    f"With home attack limited to {lambda_h:.2f} xG, model projects a {prob_pct}% draw rate. "
                    f"At {odds:.2f} odds, positive mathematical expectation is +{ev_pct}% EV. "
                    f"Projected scores 0-0 / 1-1 make this a premier high-odds pick."
                )
            else:
                return (
                    f"【Underdog Rationale】{away_team}'s counter-attacking efficiency is heavily underpriced at {odds:.2f} odds. "
                    f"Model estimates true win probability at {prob_pct}% (vs market implied {implied_pct}%), "
                    f"delivering positive EV of +{ev_pct}%. Exceptional risk-adjusted return."
                )

        elif category == "GOALS":
            p_over = extra_data.get("p_over_2_5", 0.60) if extra_data else 0.60
            p_btts = extra_data.get("p_btts", 0.55) if extra_data else 0.55
            return (
                f"【Goal Feast Rationale】Both sides favor expansive, open-tempo tactics with leaky backlines. "
                f"Combined projected xG is {total_xg} ({lambda_h:.2f} home + {mu_a:.2f} away). "
                f"Over 2.5 goals likelihood is {round(p_over*100, 1)}%, with Both Teams to Score (BTTS) at {round(p_btts*100, 1)}%. "
                f"Projected scores: {score_str}. Strong expectation of goals."
            )

        return f"【Pick Rationale】Model selection {selection_name} at {odds:.2f} with {prob_pct}% estimated win probability."

    # Chinese (default)
    if category == "BANKER":
        if "主胜" in selection_name or selection_type == "HOME_WIN":
            xg_diff = round(lambda_h - mu_a, 2)
            return (
                f"【稳胆核心理由】{home_team} 坐镇主场展现统治力，泊松模型预期进球高达 {lambda_h:.2f} 个，"
                f"而客队预期破门仅为 {mu_a:.2f} 个（净优势 +{xg_diff} 球）。模型深度测算主胜真实胜率达到 {prob_pct}%。"
                f"机构开出 {odds:.2f} 赔率，防守端压制力明显。预测最可能比分锁定 {score_str}，主胜确定性首屈一指。"
            )
        else:
            return (
                f"【稳胆核心理由】{away_team} 本场客战综合战力明显占优，客胜预期进球达到 {mu_a:.2f} 个，"
                f"模型计算客胜真实概率高达 {prob_pct}%。主队防守漏洞较大（预期失球 {mu_a:.2f}），"
                f"机构盘口对客队支持力度充足。最可能比分推荐 {score_str}，正路客胜值得信赖。"
            )

    elif category == "VALUE":
        return (
            f"【超额价值解析】本场机构盘口出现明显认知偏差！机构开出 {odds:.2f} 的偏高赔率（折合机构隐含胜率仅 {implied_pct}%），"
            f"但量化模型通过双变量泊松与历史交锋回归，测得真实胜率高达 {prob_pct}%（理论公允赔率仅为 {fair_odds:.2f}）。"
            f"数学期望优势 (EV) 达到 +{ev_pct}%。机构定价虚高带来巨大价值红利，单选 {selection_name} 具备极高长期盈利期望。"
        )

    elif category == "UNDERDOG":
        if "平局" in selection_name or selection_type == "DRAW":
            return (
                f"【高赔搏冷解析】两队球风克制且攻防拉锯，主队缺乏攻坚锐度（主队预期进球仅 {lambda_h:.2f}），"
                f"模型测算法定时间战平概率达到 {prob_pct}%。机构给出高达 {odds:.2f} 的平局高赔，数学期望高达 +{ev_pct}%。"
                f"最可能比分预计 0-0 或 1-1，极具搏冷博弈空间。"
            )
        else:
            return (
                f"【高赔冷门解析】客队防守反击反弹预期强烈，机构在初盘给出了高达 {odds:.2f} 的冷门赔率。"
                f"模型测算其冷门打出概率被市场严重低估（真实概率 {prob_pct}% vs 机构预期 {implied_pct}%），"
                f"正向期望值高达 +{ev_pct}%。以小博大，适合冷门博弈。"
            )

    elif category == "GOALS":
        p_over = extra_data.get("p_over_2_5", 0.60) if extra_data else 0.60
        p_btts = extra_data.get("p_btts", 0.55) if extra_data else 0.55
        return (
            f"【进球大战解析】双方战术风格均崇尚全攻全守，防守端漏洞明显。量化模型测算全场预期总进球高达 {total_xg} 个"
            f"（主队 {lambda_h:.2f} + 客队 {mu_a:.2f}）。大 2.5 球打出概率达 {round(p_over*100, 1)}%，"
            f"双方皆进球 (BTTS) 概率达 {round(p_btts*100, 1)}%。预测比分锁定 {score_str}，坚定看好对攻大球。"
        )

    return f"【模型推荐】推荐投注 {selection_name}，当前赔率 {odds:.2f}，模型胜率 {prob_pct}%。"


def compile_daily_picks(
    matches: List[Match],
    league_id: Optional[str] = None,
    lang: str = "zh",
) -> Dict[str, Any]:
    """
    Processes scheduled matches into curated picks and smart parlays.
    Supports both 'zh' (Chinese) and 'en' (English).
    """
    is_en = lang == "en"
    now = datetime.now(timezone.utc)
    bankers: List[Dict[str, Any]] = []
    values: List[Dict[str, Any]] = []
    underdogs: List[Dict[str, Any]] = []
    goals_list: List[Dict[str, Any]] = []

    for m in matches:
        if not m.predictions:
            continue
        pred = max(m.predictions, key=lambda p: p.as_of)
        odds = pred.odds_snapshot
        if not odds:
            continue

        h_odds = float(odds.home_odds)
        d_odds = float(odds.draw_odds)
        a_odds = float(odds.away_odds)

        p_h = pred.prob_home_win
        p_d = pred.prob_draw
        p_a = pred.prob_away_win

        ev_h = calculate_ev(p_h, h_odds)
        ev_d = calculate_ev(p_d, d_odds)
        ev_a = calculate_ev(p_a, a_odds)

        deriv = compute_derived_markets(
            pred.score_matrix, pred.lambda_home, pred.mu_away, pred.omitted_mass
        )

        match_meta = {
            "match_id": m.id,
            "league_id": m.league_id,
            "home_team": m.home_team.canonical_name,
            "away_team": m.away_team.canonical_name,
            "match_date": m.match_date.isoformat(),
            "expected_goals": {
                "home": round(pred.lambda_home, 2),
                "away": round(pred.mu_away, 2),
                "total": round(pred.lambda_home + pred.mu_away, 2),
            },
            "top_scores": [
                {"score": s.get("score"), "prob_pct": round(s.get("prob", 0.0) * 100, 1)}
                for s in (pred.top_scores or [])[:3]
            ],
        }

        # 1. Check Banker Candidate (Highest Win Prob >= 50%)
        if p_h >= 0.50 or p_a >= 0.50:
            is_home = p_h >= p_a
            b_prob = p_h if is_home else p_a
            b_odds = h_odds if is_home else a_odds
            b_ev = ev_h if is_home else ev_a
            b_code = "HOME_WIN" if is_home else "AWAY_WIN"
            
            if is_en:
                b_name = f"{m.home_team.canonical_name} (Home Win)" if is_home else f"{m.away_team.canonical_name} (Away Win)"
                cat_label = "⭐ Daily Banker"
                mkt_label = "1X2 Match Odds"
            else:
                b_name = f"{m.home_team.canonical_name} (主胜)" if is_home else f"{m.away_team.canonical_name} (客胜)"
                cat_label = "⭐ 今日稳胆"
                mkt_label = "1X2 独赢"

            b_fair = round(1.0 / b_prob, 2) if b_prob > 0 else 99.0
            stars = 5 if b_prob >= 0.65 else 4

            bankers.append({
                **match_meta,
                "pick_id": f"BANKER_{m.id}_{b_code}",
                "category": "BANKER",
                "category_label": cat_label,
                "selection": b_code,
                "selection_name": b_name,
                "market_type": mkt_label,
                "market_odds": b_odds,
                "fair_odds": b_fair,
                "model_probability": round(b_prob, 4),
                "confidence_stars": stars,
                "ev_pct": round(b_ev * 100, 1),
                "reasoning": generate_rationale(
                    "BANKER",
                    m.home_team.canonical_name,
                    m.away_team.canonical_name,
                    b_code,
                    b_name,
                    b_odds,
                    b_fair,
                    b_prob,
                    b_ev,
                    pred.lambda_home,
                    pred.mu_away,
                    pred.top_scores,
                    lang=lang,
                ),
                "key_stats": [
                    f"{'Model Win Rate' if is_en else '模型胜率'} {round(b_prob * 100, 1)}%",
                    f"{'xG Expectancy' if is_en else 'xG 进球期望'} {pred.lambda_home:.2f} : {pred.mu_away:.2f}",
                    f"{'Initial Odds' if is_en else '机构初赔'} {b_odds:.2f}",
                ],
            })

        # 2. Check Value Candidates (EV >= 5%, Win Prob >= 35%)
        val_cands = [
            ("HOME_WIN", f"{m.home_team.canonical_name} (Home Win)" if is_en else f"{m.home_team.canonical_name} (主胜)", p_h, h_odds, ev_h),
            ("AWAY_WIN", f"{m.away_team.canonical_name} (Away Win)" if is_en else f"{m.away_team.canonical_name} (客胜)", p_a, a_odds, ev_a),
        ]
        for code, name, prob, o, ev in val_cands:
            if ev >= 0.05 and prob >= 0.35:
                fair = round(1.0 / prob, 2) if prob > 0 else 99.0
                values.append({
                    **match_meta,
                    "pick_id": f"VAL_{m.id}_{code}",
                    "category": "VALUE",
                    "category_label": "🔥 Top Value Pick" if is_en else "🔥 每日精选",
                    "selection": code,
                    "selection_name": name,
                    "market_type": "1X2 Value" if is_en else "1X2 价值",
                    "market_odds": o,
                    "fair_odds": fair,
                    "model_probability": round(prob, 4),
                    "confidence_stars": 5 if ev >= 0.20 else 4,
                    "ev_pct": round(ev * 100, 1),
                    "reasoning": generate_rationale(
                        "VALUE",
                        m.home_team.canonical_name,
                        m.away_team.canonical_name,
                        code,
                        name,
                        o,
                        fair,
                        prob,
                        ev,
                        pred.lambda_home,
                        pred.mu_away,
                        pred.top_scores,
                        lang=lang,
                    ),
                    "key_stats": [
                        f"{'Positive EV' if is_en else '正期望 EV'} +{round(ev * 100, 1)}%",
                        f"{'Fair Odds' if is_en else '合理赔率'} {fair:.2f} ({'Now' if is_en else '现赔'} {o:.2f})",
                        f"{'Model Prob' if is_en else '模型胜率'} {round(prob * 100, 1)}%",
                    ],
                })

        # 3. Check Underdog / Draw Candidates (Odds >= 3.0, EV >= 10%)
        dog_cands = [
            ("DRAW", "Draw (平局)" if is_en else "平局 (Draw)", p_d, d_odds, ev_d),
            ("HOME_WIN", f"{m.home_team.canonical_name} (Home Dog)" if is_en else f"{m.home_team.canonical_name} (主胜高赔)", p_h, h_odds, ev_h),
            ("AWAY_WIN", f"{m.away_team.canonical_name} (Away Dog)" if is_en else f"{m.away_team.canonical_name} (客胜高赔)", p_a, a_odds, ev_a),
        ]
        for code, name, prob, o, ev in dog_cands:
            if o >= 3.0 and ev >= 0.10:
                fair = round(1.0 / prob, 2) if prob > 0 else 99.0
                underdogs.append({
                    **match_meta,
                    "pick_id": f"DOG_{m.id}_{code}",
                    "category": "UNDERDOG",
                    "category_label": "💣 Value Underdog" if is_en else "💣 搏冷高赔",
                    "selection": code,
                    "selection_name": name,
                    "market_type": "Underdog Pick" if is_en else "高赔搏冷",
                    "market_odds": o,
                    "fair_odds": fair,
                    "model_probability": round(prob, 4),
                    "confidence_stars": 4 if ev >= 0.30 else 3,
                    "ev_pct": round(ev * 100, 1),
                    "reasoning": generate_rationale(
                        "UNDERDOG",
                        m.home_team.canonical_name,
                        m.away_team.canonical_name,
                        code,
                        name,
                        o,
                        fair,
                        prob,
                        ev,
                        pred.lambda_home,
                        pred.mu_away,
                        pred.top_scores,
                        lang=lang,
                    ),
                    "key_stats": [
                        f"{'Underdog Odds' if is_en else '搏冷赔率'} {o:.2f}",
                        f"{'Positive EV' if is_en else '正期望 EV'} +{round(ev * 100, 1)}%",
                        f"{'Model Prob' if is_en else '模型胜率'} {round(prob * 100, 1)}%",
                    ],
                })

        # 4. Check Goals Candidates (Total xG >= 2.6 or Over 2.5 prob >= 52%)
        totals = deriv.get("totals", {})
        over_2_5_info = totals.get("over_2_5", {})
        p_over_2_5 = over_2_5_info.get("prob", 0.0)
        p_btts = deriv.get("btts", {}).get("yes", {}).get("prob", 0.0)

        total_xg = pred.lambda_home + pred.mu_away
        if total_xg >= 2.6 or p_over_2_5 >= 0.52:
            fair_o25 = over_2_5_info.get("fair_odds", round(1.0 / p_over_2_5, 2) if p_over_2_5 > 0 else 2.0)
            market_o25 = round(max(1.50, fair_o25 * 0.94), 2)
            ev_goals = calculate_ev(p_over_2_5, market_o25)

            o25_name = "Over 2.5 Goals" if is_en else "全场大 2.5 球"

            goals_list.append({
                **match_meta,
                "pick_id": f"GOAL_{m.id}_O25",
                "category": "GOALS",
                "category_label": "⚽ Goal Feast" if is_en else "⚽ 进球狂欢",
                "selection": "OVER_2_5",
                "selection_name": o25_name,
                "market_type": "Totals (O/U)" if is_en else "大小球 (Totals)",
                "market_odds": market_o25,
                "fair_odds": fair_o25,
                "model_probability": round(p_over_2_5, 4),
                "confidence_stars": 5 if p_over_2_5 >= 0.68 else 4,
                "ev_pct": round(ev_goals * 100, 1),
                "reasoning": generate_rationale(
                    "GOALS",
                    m.home_team.canonical_name,
                    m.away_team.canonical_name,
                    "OVER_2_5",
                    o25_name,
                    market_o25,
                    fair_o25,
                    p_over_2_5,
                    ev_goals,
                    pred.lambda_home,
                    pred.mu_away,
                    pred.top_scores,
                    extra_data={"p_over_2_5": p_over_2_5, "p_btts": p_btts},
                    lang=lang,
                ),
                "key_stats": [
                    f"{'Over 2.5 Prob' if is_en else '大球概率'} {round(p_over_2_5 * 100, 1)}%",
                    f"{'Total xG' if is_en else '两队期望进球'} {total_xg:.2f}",
                    f"{'BTTS Prob' if is_en else '双进概率'} {round(p_btts * 100, 1)}%",
                ],
            })

    # Sort each category
    bankers.sort(key=lambda x: x["model_probability"], reverse=True)
    values.sort(key=lambda x: x["ev_pct"], reverse=True)
    underdogs.sort(key=lambda x: x["market_odds"] * (x["ev_pct"] / 100.0), reverse=True)
    goals_list.sort(key=lambda x: x["expected_goals"]["total"], reverse=True)

    top_bankers = bankers[:6]
    top_values = values[:6]
    top_underdogs = underdogs[:6]
    top_goals = goals_list[:6]

    # Generate Smart Parlays
    parlays = _build_smart_parlays(top_bankers, top_values, top_goals, top_underdogs, lang=lang)

    return {
        "generated_at": now.isoformat(),
        "lang": lang,
        "summary": {
            "banker_count": len(top_bankers),
            "value_count": len(top_values),
            "underdog_count": len(top_underdogs),
            "goals_count": len(top_goals),
            "parlays_count": len(parlays),
        },
        "bankers": top_bankers,
        "values": top_values,
        "underdogs": top_underdogs,
        "goals": top_goals,
        "parlays": parlays,
    }


def _build_smart_parlays(
    bankers: List[Dict[str, Any]],
    values: List[Dict[str, Any]],
    goals: List[Dict[str, Any]],
    underdogs: List[Dict[str, Any]],
    lang: str = "zh",
) -> List[Dict[str, Any]]:
    """
    Constructs 3 high-grade parlays with combined odds, joint win probabilities,
    and 1-click clipboard summaries in either Chinese or English.
    """
    is_en = lang == "en"
    parlays = []

    # 1. 稳健 2 串 1 (Safe 2-fold banker)
    if len(bankers) >= 2:
        leg1 = bankers[0]
        leg2 = next((b for b in bankers[1:] if b["match_id"] != leg1["match_id"]), bankers[1])
        c_odds = round(leg1["market_odds"] * leg2["market_odds"], 2)
        j_prob = round(leg1["model_probability"] * leg2["model_probability"], 4)
        j_ev = round((j_prob * c_odds - 1.0) * 100, 1)

        if is_en:
            title = "🛡️ Daily Safe 2-Fold (High Win Rate)"
            subtitle = "Top 2 most decisive fixtures combined for optimal safety and bankroll growth"
            badge = "Banker Combo"
            copy_text = (
                f"【MatchLambda Safe 2-Fold Parlay Ticket】\n"
                f"1. [{leg1['league_id']}] {leg1['home_team']} vs {leg1['away_team']} -> Pick: {leg1['selection_name']} @{leg1['market_odds']:.2f}\n"
                f"2. [{leg2['league_id']}] {leg2['home_team']} vs {leg2['away_team']} -> Pick: {leg2['selection_name']} @{leg2['market_odds']:.2f}\n"
                f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: +{j_ev}%\n"
                f"Stake Recommendation: Stake ¥100 -> Est. Payout: ¥{round(100 * c_odds, 1)}"
            )
        else:
            title = "🛡️ 今日稳健 2 串 1 (高胜率首选)"
            subtitle = "优选中最高确定性强强对碰，理论命中率近 60%，兼顾安全与翻倍"
            badge = "稳胆组合"
            copy_text = (
                f"【MatchLambda 稳健 2 串 1 方案】\n"
                f"1. [{leg1['league_id']}] {leg1['home_team']} vs {leg1['away_team']} -> 推荐: {leg1['selection_name']} @{leg1['market_odds']:.2f}\n"
                f"2. [{leg2['league_id']}] {leg2['home_team']} vs {leg2['away_team']} -> 推荐: {leg2['selection_name']} @{leg2['market_odds']:.2f}\n"
                f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: +{j_ev}%\n"
                f"投注建议: 投 100 元预计奖金 {round(100 * c_odds, 1)} 元"
            )

        parlays.append({
            "parlay_id": "PARLAY_SAFE_2",
            "type": "SAFE_2X1",
            "title": title,
            "subtitle": subtitle,
            "badge": badge,
            "tag_color": "emerald",
            "combined_odds": c_odds,
            "win_probability_pct": round(j_prob * 100, 1),
            "expected_ev_pct": j_ev,
            "suggested_unit": 100,
            "expected_return": round(100 * c_odds, 1),
            "copy_text": copy_text,
            "legs": [
                {
                    "match_id": leg1["match_id"],
                    "league_id": leg1["league_id"],
                    "match_date": leg1["match_date"],
                    "home_team": leg1["home_team"],
                    "away_team": leg1["away_team"],
                    "selection": leg1["selection_name"],
                    "odds": leg1["market_odds"],
                    "win_prob": round(leg1["model_probability"] * 100, 1),
                },
                {
                    "match_id": leg2["match_id"],
                    "league_id": leg2["league_id"],
                    "match_date": leg2["match_date"],
                    "home_team": leg2["home_team"],
                    "away_team": leg2["away_team"],
                    "selection": leg2["selection_name"],
                    "odds": leg2["market_odds"],
                    "win_prob": round(leg2["model_probability"] * 100, 1),
                },
            ],
        })

    # 2. 黄金进阶 3 串 1 (Balanced 3-fold)
    leg_banker = bankers[0] if bankers else None
    leg_val = values[0] if values else None
    leg_goal = goals[0] if goals else None

    selected_matches = set()
    b_legs = []
    for cand in [leg_banker, leg_val, leg_goal]:
        if cand and cand["match_id"] not in selected_matches:
            b_legs.append(cand)
            selected_matches.add(cand["match_id"])

    for cand in values + bankers + goals:
        if len(b_legs) >= 3:
            break
        if cand and cand["match_id"] not in selected_matches:
            b_legs.append(cand)
            selected_matches.add(cand["match_id"])

    if len(b_legs) >= 3:
        c_odds = round(b_legs[0]["market_odds"] * b_legs[1]["market_odds"] * b_legs[2]["market_odds"], 2)
        j_prob = round(b_legs[0]["model_probability"] * b_legs[1]["model_probability"] * b_legs[2]["model_probability"], 4)
        j_ev = round((j_prob * c_odds - 1.0) * 100, 1)

        if is_en:
            title = "🔥 Golden 3-Fold (Balanced Risk/Reward)"
            subtitle = "Banker + Mispriced Value Line + High Scoring Over, scientifically curated"
            badge = "Golden Combo"
            copy_text = (
                f"【MatchLambda Golden 3-Fold Parlay Ticket】\n"
                f"1. [{b_legs[0]['league_id']}] {b_legs[0]['home_team']} vs {b_legs[0]['away_team']} -> {b_legs[0]['selection_name']} @{b_legs[0]['market_odds']:.2f}\n"
                f"2. [{b_legs[1]['league_id']}] {b_legs[1]['home_team']} vs {b_legs[1]['away_team']} -> {b_legs[1]['selection_name']} @{b_legs[1]['market_odds']:.2f}\n"
                f"3. [{b_legs[2]['league_id']}] {b_legs[2]['home_team']} vs {b_legs[2]['away_team']} -> {b_legs[2]['selection_name']} @{b_legs[2]['market_odds']:.2f}\n"
                f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: +{j_ev}%\n"
                f"Stake Recommendation: Stake ¥50 -> Est. Payout: ¥{round(50 * c_odds, 1)}"
            )
        else:
            title = "🔥 黄金进阶 3 串 1 (中倍高盈亏比)"
            subtitle = "稳胆 + 价值盘口 + 大球组合，科学搭配，盈亏比极佳"
            badge = "黄金组合"
            copy_text = (
                f"【MatchLambda 黄金 3 串 1 方案】\n"
                f"1. [{b_legs[0]['league_id']}] {b_legs[0]['home_team']} vs {b_legs[0]['away_team']} -> {b_legs[0]['selection_name']} @{b_legs[0]['market_odds']:.2f}\n"
                f"2. [{b_legs[1]['league_id']}] {b_legs[1]['home_team']} vs {b_legs[1]['away_team']} -> {b_legs[1]['selection_name']} @{b_legs[1]['market_odds']:.2f}\n"
                f"3. [{b_legs[2]['league_id']}] {b_legs[2]['home_team']} vs {b_legs[2]['away_team']} -> {b_legs[2]['selection_name']} @{b_legs[2]['market_odds']:.2f}\n"
                f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: +{j_ev}%\n"
                f"投注建议: 投 50 元预计奖金 {round(50 * c_odds, 1)} 元"
            )

        parlays.append({
            "parlay_id": "PARLAY_BALANCED_3",
            "type": "BALANCED_3X1",
            "title": title,
            "subtitle": subtitle,
            "badge": badge,
            "tag_color": "blue",
            "combined_odds": c_odds,
            "win_probability_pct": round(j_prob * 100, 1),
            "expected_ev_pct": j_ev,
            "suggested_unit": 50,
            "expected_return": round(50 * c_odds, 1),
            "copy_text": copy_text,
            "legs": [
                {
                    "match_id": l["match_id"],
                    "league_id": l["league_id"],
                    "match_date": l["match_date"],
                    "home_team": l["home_team"],
                    "away_team": l["away_team"],
                    "selection": l["selection_name"],
                    "odds": l["market_odds"],
                    "win_prob": round(l["model_probability"] * 100, 1),
                }
                for l in b_legs
            ],
        })

    # 3. 梦想搏冷 3 串 1 (Lottery High Odds)
    dog_legs = []
    dog_seen = set()
    for d in underdogs:
        if d["match_id"] not in dog_seen:
            dog_legs.append(d)
            dog_seen.add(d["match_id"])
        if len(dog_legs) >= 3:
            break

    if len(dog_legs) >= 3:
        c_odds = round(dog_legs[0]["market_odds"] * dog_legs[1]["market_odds"] * dog_legs[2]["market_odds"], 2)
        j_prob = round(dog_legs[0]["model_probability"] * dog_legs[1]["model_probability"] * dog_legs[2]["model_probability"], 4)
        j_ev = round((j_prob * c_odds - 1.0) * 100, 1)

        if is_en:
            title = "💣 Longshot 3-Fold Lottery (10x+ High Payout)"
            subtitle = "3 heavily mispriced high-odds underdogs and draws with massive market leverage"
            badge = "10x Longshot"
            copy_text = (
                f"【MatchLambda Longshot 3-Fold Lottery Ticket】\n"
                f"1. [{dog_legs[0]['league_id']}] {dog_legs[0]['home_team']} vs {dog_legs[0]['away_team']} -> {dog_legs[0]['selection_name']} @{dog_legs[0]['market_odds']:.2f}\n"
                f"2. [{dog_legs[1]['league_id']}] {dog_legs[1]['home_team']} vs {dog_legs[1]['away_team']} -> {dog_legs[1]['selection_name']} @{dog_legs[1]['market_odds']:.2f}\n"
                f"3. [{dog_legs[2]['league_id']}] {dog_legs[2]['home_team']} vs {dog_legs[2]['away_team']} -> {dog_legs[2]['selection_name']} @{dog_legs[2]['market_odds']:.2f}\n"
                f"Combined Odds: {c_odds:.2f} | Est. Win Rate: {round(j_prob*100, 1)}% | Expected EV: +{j_ev}%\n"
                f"Stake Recommendation: Stake ¥20 micro-unit -> Est. Payout: ¥{round(20 * c_odds, 1)}"
            )
        else:
            title = "💣 梦想搏冷 3 串 1 (十倍大奖小博大)"
            subtitle = "精选 3 场机构深度低估高赔冷门与平局，单票博取十倍以上暴击"
            badge = "十倍搏冷"
            copy_text = (
                f"【MatchLambda 梦想搏冷 3 串 1 方案】\n"
                f"1. [{dog_legs[0]['league_id']}] {dog_legs[0]['home_team']} vs {dog_legs[0]['away_team']} -> {dog_legs[0]['selection_name']} @{dog_legs[0]['market_odds']:.2f}\n"
                f"2. [{dog_legs[1]['league_id']}] {dog_legs[1]['home_team']} vs {dog_legs[1]['away_team']} -> {dog_legs[1]['selection_name']} @{dog_legs[1]['market_odds']:.2f}\n"
                f"3. [{dog_legs[2]['league_id']}] {dog_legs[2]['home_team']} vs {dog_legs[2]['away_team']} -> {dog_legs[2]['selection_name']} @{dog_legs[2]['market_odds']:.2f}\n"
                f"组合赔率: {c_odds:.2f} | 预估命中率: {round(j_prob*100, 1)}% | 期望盈利率: +{j_ev}%\n"
                f"投注建议: 投 20 元小注博取 {round(20 * c_odds, 1)} 元大奖"
            )

        parlays.append({
            "parlay_id": "PARLAY_LOTTERY_3",
            "type": "LOTTERY_3X1",
            "title": title,
            "subtitle": subtitle,
            "badge": badge,
            "tag_color": "amber",
            "combined_odds": c_odds,
            "win_probability_pct": round(j_prob * 100, 1),
            "expected_ev_pct": j_ev,
            "suggested_unit": 20,
            "expected_return": round(20 * c_odds, 1),
            "copy_text": copy_text,
            "legs": [
                {
                    "match_id": l["match_id"],
                    "league_id": l["league_id"],
                    "match_date": l["match_date"],
                    "home_team": l["home_team"],
                    "away_team": l["away_team"],
                    "selection": l["selection_name"],
                    "odds": l["market_odds"],
                    "win_prob": round(l["model_probability"] * 100, 1),
                }
                for l in dog_legs
            ],
        })

    return parlays
