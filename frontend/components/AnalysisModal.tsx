"use client";

import React, { useEffect, useRef, useState } from "react";
import { X, AlertTriangle, Activity, Flame, Layers, Calculator, ShieldCheck, TrendingUp } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { lockBodyScroll } from "@/lib/scrollLock";
import { trapTabKey } from "@/lib/focusTrap";

interface AnalysisModalProps {
  matchId: string | null;
  fixture?: any;
  onClose: () => void;
}

function finiteNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const n = Number(value);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

// Human-readable names for The Odds API bookmaker keys.
const BOOKMAKER_LABELS: Record<string, string> = {
  pinnacle: "Pinnacle",
  betfair_ex_uk: "Betfair Exchange",
  betfair: "Betfair",
  bet365: "Bet365",
  williamhill: "William Hill",
};

function fmtBookmaker(value: unknown): string {
  if (value == null || value === "") return "—";
  const key = String(value).toLowerCase();
  return BOOKMAKER_LABELS[key] || String(value).toUpperCase();
}

function fmtFixed(value: unknown, digits: number): string {
  const n = finiteNumber(value);
  return n == null ? "—" : n.toFixed(digits);
}

function fmtPct(value: unknown, digits = 1): string {
  const n = finiteNumber(value);
  return n == null ? "—" : `${(n * 100).toFixed(digits)}%`;
}

function fmtSignedMoney(value: number): string {
  if (!Number.isFinite(value)) return "—";
  if (value > 0) return `+$${value.toFixed(2)}`;
  if (value < 0) return `-$${Math.abs(value).toFixed(2)}`;
  return `$${value.toFixed(2)}`;
}

function probOddsText(node: any): string {
  if (!node || typeof node !== "object") return "—";
  const pct = fmtPct(node.prob, 1);
  const odds = finiteNumber(node.fair_odds);
  const oddsText = odds != null ? String(odds) : node.fair_odds == null || node.fair_odds === "" ? "—" : String(node.fair_odds);
  if (pct === "—" && oddsText === "—") return "—";
  return `${pct} (${oddsText})`;
}

function fmtUtc(value: unknown): string {
  if (typeof value !== "string" && typeof value !== "number") return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toUTCString();
}

function fmtLocal(value: unknown, lang: string): string {
  if (value == null || value === "") return "";
  const d = new Date(value as string);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(lang === "en" ? "en-US" : "zh-CN");
}

export const AnalysisModal: React.FC<AnalysisModalProps> = ({ matchId, fixture, onClose }) => {
  const { lang, t } = useI18n();
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>("1X2");
  const [bankrollInput, setBankrollInput] = useState("5000");
  const [bankroll, setBankroll] = useState(5000);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const tRef = useRef(t);
  tRef.current = t;
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setActiveTab("1X2");
  }, [matchId]);

  useEffect(() => {
    if (!matchId) return;
    const release = lockBodyScroll();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
      if (e.key === "Tab") trapTabKey(e, dialogRef.current);
    };
    window.addEventListener("keydown", handleKeyDown);
    const focusId = window.setTimeout(() => {
      dialogRef.current?.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }, 0);
    return () => {
      release();
      window.removeEventListener("keydown", handleKeyDown);
      window.clearTimeout(focusId);
    };
  }, [matchId]);

  useEffect(() => {
    if (!matchId) {
      setLoading(false);
      return;
    }
    const controller = new AbortController();
    let active = true;
    setLoading(true);
    setError(null);
    setData(null);
    apiRequest<any>(`/matches/${matchId}/analysis`, { signal: controller.signal })
      .then((res) => {
        if (!active) return;
        setData(res);
      })
      .catch((err: any) => {
        if (!active || controller.signal.aborted || err?.code === "ABORTED") return;
        setError(err?.message || tRef.current("modal.loadFailed"));
      })
      .finally(() => {
        if (active && !controller.signal.aborted) setLoading(false);
      });
    return () => {
      active = false;
      controller.abort(new Error("Match modal unmounted"));
    };
  }, [matchId]);

  if (!matchId) return null;

  const deriv = data?.derivatives;
  const homeName = fixture?.home_team?.name;
  const awayName = fixture?.away_team?.name;
  const title = homeName && awayName ? `${homeName} vs ${awayName}` : t("modal.depthAnalysis");
  const kickoff = fmtLocal(fixture?.match_date, lang);
  const outcomes = Array.isArray(data?.comparison?.outcomes) ? data.comparison.outcomes : [];

  const commitBankroll = () => {
    const n = Number(bankrollInput);
    const clamped = Number.isFinite(n) ? Math.min(1_000_000, Math.max(10, n)) : 10;
    setBankroll(clamped);
    setBankrollInput(String(clamped));
  };

  const tabs = [
    { id: "1X2", label: t("modal.tabs.matchOdds") },
    { id: "TOTALS", label: t("modal.tabs.totals") },
    { id: "BTTS", label: t("modal.tabs.btts") },
    { id: "HANDICAP", label: t("modal.tabs.handicap") },
    { id: "DC", label: t("modal.tabs.doubleChance") },
    { id: "MATRIX", label: t("modal.tabs.matrix") },
    { id: "STAKE", label: t("modal.tabs.kelly") },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 md:p-6 bg-black/85 backdrop-blur-md"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCloseRef.current();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="analysis-dialog-title"
        className="bg-[#0f1523] border border-gray-800 rounded-2xl w-full max-w-4xl max-h-[92vh] flex flex-col shadow-2xl relative overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 sm:px-7 py-4 border-b border-gray-800 bg-[#0d121e] z-20 flex-shrink-0">
          <div className="flex items-center space-x-3 overflow-hidden">
            <div className="p-2 rounded-lg bg-blue-500/10 border border-blue-500/20 text-blue-400 flex-shrink-0">
              <Activity className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 id="analysis-dialog-title" className="text-base sm:text-lg font-bold text-white truncate">
                  {title}
                </h3>
                {fixture?.league_id && (
                  <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 flex-shrink-0">
                    {fixture.league_id}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 font-mono truncate">
                {kickoff ? `${kickoff} · ` : ""}
                ID: {matchId}
              </p>
            </div>
          </div>

          <button
            type="button"
            data-autofocus
            onClick={() => onCloseRef.current()}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 hover:text-white transition text-xs font-semibold flex-shrink-0 ml-3 border border-gray-700 shadow-sm"
            aria-label={t("modal.close")}
          >
            <span>{t("modal.close")}</span>
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center space-x-1 px-5 sm:px-7 pt-3 pb-2 border-b border-gray-800/80 bg-[#0a0e18] overflow-x-auto text-xs font-mono scrollbar-none flex-shrink-0">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg font-medium whitespace-nowrap transition ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white font-bold shadow-md shadow-blue-500/20"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/60"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto p-5 sm:p-7 space-y-6">
          {loading ? (
            <div className="py-24 text-center">
              <div className="w-10 h-10 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
              <p className="text-xs text-gray-400 font-mono">{t("modal.loading")}</p>
            </div>
          ) : error ? (
            <div className="py-16 text-center">
              <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-3" />
              <h4 className="text-white font-bold text-base mb-1">{t("modal.accessRestricted")}</h4>
              <p className="text-xs text-gray-400 max-w-sm mx-auto">{error}</p>
            </div>
          ) : data ? (
            <div className="space-y-6">
              <div className="border-b border-gray-800 pb-4">
                <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                  <span className="text-xs font-mono font-bold text-blue-400 bg-blue-500/10 px-2.5 py-1 rounded border border-blue-500/20">
                    {data.match_id ?? matchId}
                  </span>
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-xs px-2.5 py-0.5 rounded font-mono font-bold flex items-center ${
                        data.data_status === "AVAILABLE"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : data.data_status === "STALE"
                            ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                            : "bg-red-500/10 text-red-400 border border-red-500/20"
                      }`}
                    >
                      <Activity className="w-3.5 h-3.5 mr-1" /> {data.data_status ?? "—"}
                    </span>
                    {data.reason && (
                      <span className="text-[11px] font-mono text-gray-400 bg-gray-800 px-2 py-0.5 rounded">
                        {data.reason}
                      </span>
                    )}
                  </div>
                </div>

                {data.prediction && (
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-3 text-xs font-mono">
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">{t("modal.lambdaHome")}</span>
                      <span className="font-bold text-white text-sm">
                        {fmtFixed(data.prediction?.lambda_home, 3)} {t("modal.goalsUnit")}
                      </span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">{t("modal.muAway")}</span>
                      <span className="font-bold text-white text-sm">
                        {fmtFixed(data.prediction?.mu_away, 3)} {t("modal.goalsUnit")}
                      </span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">{t("modal.rho")}</span>
                      <span className="font-bold text-white text-sm">
                        {fmtFixed(data.prediction?.rho, 4)} {t("modal.rhoUnit")}
                      </span>
                    </div>
                    <div className="bg-[#090d16] p-2.5 rounded-lg border border-gray-800/80">
                      <span className="text-gray-500 block text-[10px]">{t("modal.expectedTotal")}</span>
                      <span className="font-bold text-blue-400 text-sm">
                        {finiteNumber(data.prediction?.lambda_home) != null &&
                        finiteNumber(data.prediction?.mu_away) != null
                          ? (
                              (finiteNumber(data.prediction?.lambda_home) as number) +
                              (finiteNumber(data.prediction?.mu_away) as number)
                            ).toFixed(2)
                          : "—"}{" "}
                        {t("modal.goalsShort")}
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {activeTab === "1X2" &&
                (outcomes.length > 0 ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                        <Flame className="w-4 h-4 mr-1.5 text-blue-400" /> {t("modal.match1x2Title")}
                      </h4>
                      <span className="text-[11px] text-gray-400 font-mono">
                        {t("modal.bookmakerLine", {
                          book: fmtBookmaker(data.comparison?.bookmaker),
                          method: data.comparison?.dejuice_method
                            ? String(data.comparison.dejuice_method)
                            : "—",
                        })}
                      </span>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs font-mono">
                        <thead>
                          <tr className="border-b border-gray-800 text-gray-400 text-[11px]">
                            <th className="pb-2">{t("modal.outcome")}</th>
                            <th className="pb-2">{t("modal.modelProb")}</th>
                            <th className="pb-2">{t("modal.marketProb")}</th>
                            <th className="pb-2">{t("modal.decimalOdds")}</th>
                            <th className="pb-2">{t("modal.expectedValue")}</th>
                            <th className="pb-2">{t("modal.halfKelly")}</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800/60">
                          {outcomes.map((item: any, idx: number) => {
                            const ev = finiteNumber(item?.ev);
                            const half = finiteNumber(item?.half_kelly);
                            const isValue = ev != null && ev >= 0.05;
                            return (
                              <tr key={item?.outcome ?? idx} className={isValue ? "bg-emerald-500/5" : ""}>
                                <td className="py-3 font-bold text-white text-sm">{item?.outcome ?? "—"}</td>
                                <td className="py-3 text-blue-400 font-semibold">{fmtPct(item?.model_prob, 2)}</td>
                                <td className="py-3 text-gray-400">{fmtPct(item?.market_prob, 2)}</td>
                                <td className="py-3 text-white font-bold">{fmtFixed(item?.odds, 2)}</td>
                                <td className="py-3">
                                  <span
                                    className={`px-2 py-0.5 rounded font-bold ${
                                      isValue
                                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                                        : ev != null && ev > 0
                                          ? "text-blue-400"
                                          : "text-gray-500"
                                    }`}
                                  >
                                    {ev == null ? "—" : `${ev > 0 ? "+" : ""}${(ev * 100).toFixed(2)}%`}
                                  </span>
                                </td>
                                <td className="py-3 text-gray-300">
                                  {half == null ? "—" : half > 0 ? `${(half * 100).toFixed(2)}%` : "0.0%"}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                ))}

              {activeTab === "TOTALS" && (
                deriv?.totals ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <TrendingUp className="w-4 h-4 mr-1.5 text-emerald-400" /> {t("modal.totalsTitle")}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                      {[
                        ["line15", "over_1_5", "under_1_5", false],
                        ["line25", "over_2_5", "under_2_5", true],
                        ["line35", "over_3_5", "under_3_5", false],
                      ].map(([labelKey, overKey, underKey, highlight]) => (
                        <div
                          key={String(overKey)}
                          className={`bg-[#0f1523] border p-4 rounded-xl space-y-3 font-mono ${
                            highlight ? "border-blue-500/30 shadow-lg shadow-blue-500/5" : "border-gray-800"
                          }`}
                        >
                          <span className={`text-xs font-bold block ${highlight ? "text-emerald-400" : "text-blue-400"}`}>
                            {t(`modal.${labelKey}`)}
                          </span>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-gray-300">{t("modal.over")}:</span>
                            <span className="text-emerald-400 font-bold">
                              {probOddsText(deriv.totals?.[overKey as string])}
                            </span>
                          </div>
                          <div className="flex justify-between items-center text-xs">
                            <span className="text-gray-300">{t("modal.under")}:</span>
                            <span className="text-gray-400 font-bold">
                              {probOddsText(deriv.totals?.[underKey as string])}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                )
              )}

              {activeTab === "BTTS" && (
                deriv?.btts ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Activity className="w-4 h-4 mr-1.5 text-indigo-400" /> {t("modal.bttsTitle")}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono">
                      <div className="bg-[#0f1523] border border-emerald-500/30 p-5 rounded-xl flex items-center justify-between">
                        <div>
                          <span className="text-emerald-400 font-bold text-base block">{t("modal.bttsYes")}</span>
                          <span className="text-xs text-gray-400">{t("modal.bttsYesHint")}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-2xl font-black text-white">{fmtPct(deriv.btts?.yes?.prob, 1)}</span>
                          <span className="text-xs text-gray-400 block">
                            {t("modal.fairOdds")}: {deriv.btts?.yes?.fair_odds ?? "—"}
                          </span>
                        </div>
                      </div>
                      <div className="bg-[#0f1523] border border-gray-800 p-5 rounded-xl flex items-center justify-between">
                        <div>
                          <span className="text-gray-300 font-bold text-base block">{t("modal.bttsNo")}</span>
                          <span className="text-xs text-gray-400">{t("modal.bttsNoHint")}</span>
                        </div>
                        <div className="text-right">
                          <span className="text-2xl font-black text-white">{fmtPct(deriv.btts?.no?.prob, 1)}</span>
                          <span className="text-xs text-gray-400 block">
                            {t("modal.fairOdds")}: {deriv.btts?.no?.fair_odds ?? "—"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                )
              )}

              {activeTab === "HANDICAP" && (
                deriv?.asian_handicap ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <ShieldCheck className="w-4 h-4 mr-1.5 text-blue-400" /> {t("modal.handicapTitle")}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 font-mono text-xs">
                      {[
                        ["home_minus_0_5", "homeMinus05", "homeMinus05Hint"],
                        ["home_plus_0_5", "homePlus05", "homePlus05Hint"],
                        ["home_minus_1_5", "homeMinus15", "homeMinus15Hint"],
                        ["home_plus_1_5", "homePlus15", "homePlus15Hint"],
                      ].map(([key, labelKey, hintKey]) => {
                        const node = deriv.asian_handicap?.[key];
                        return (
                          <div key={key} className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex justify-between items-center">
                            <div>
                              <span className="font-bold text-white block">{t(`modal.${labelKey}`)}</span>
                              <span className="text-[10px] text-gray-400">{t(`modal.${hintKey}`)}</span>
                            </div>
                            <div className="text-right">
                              <span className="text-base font-bold text-blue-400">{fmtPct(node?.prob, 1)}</span>
                              <span className="text-[10px] text-gray-400 block">
                                {t("modal.fair")}: {node?.fair_odds ?? "—"}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                )
              )}

              {activeTab === "DC" && (
                deriv?.double_chance ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4 font-mono text-xs">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Layers className="w-4 h-4 mr-1.5 text-amber-400" /> {t("modal.dcTitle")}
                    </h4>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                      {[
                        ["1x", "dc1x"],
                        ["x2", "dcX2"],
                        ["12", "dc12"],
                      ].map(([key, labelKey]) => {
                        const node = deriv.double_chance?.[key];
                        return (
                          <div key={key} className="bg-[#0f1523] p-3 rounded-lg border border-gray-800">
                            <span className="text-gray-400 block">{t(`modal.${labelKey}`)}</span>
                            <span className="text-lg font-bold text-white mt-1 block">{fmtPct(node?.prob, 1)}</span>
                            <span className="text-[10px] text-gray-500">
                              {t("modal.fairOdds")}: {node?.fair_odds ?? "—"}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                    {deriv.draw_no_bet && (
                      <div className="pt-2">
                        <h5 className="text-xs font-bold text-gray-400 mb-2">{t("modal.dnbTitle")}</h5>
                        <div className="grid grid-cols-2 gap-3">
                          <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800 flex justify-between items-center">
                            <span>{t("modal.dnbHome")}:</span>
                            <span className="font-bold text-blue-400">
                              {fmtPct(deriv.draw_no_bet?.home?.prob, 1)} ({t("modal.fair")}:{" "}
                              {deriv.draw_no_bet?.home?.fair_odds ?? "—"})
                            </span>
                          </div>
                          <div className="bg-[#0f1523] p-3 rounded-lg border border-gray-800 flex justify-between items-center">
                            <span>{t("modal.dnbAway")}:</span>
                            <span className="font-bold text-indigo-400">
                              {fmtPct(deriv.draw_no_bet?.away?.prob, 1)} ({t("modal.fair")}:{" "}
                              {deriv.draw_no_bet?.away?.fair_odds ?? "—"})
                            </span>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                )
              )}

              {activeTab === "MATRIX" && (
                data.prediction ? (
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    <div className="lg:col-span-2 bg-[#090d16] rounded-xl border border-gray-800 p-5">
                      <div className="flex items-center justify-between mb-3">
                        <h4 className="text-sm font-bold text-white uppercase tracking-wider">{t("modal.matrixTitle")}</h4>
                        <span className="text-[11px] font-mono text-gray-400">
                          {t("modal.omittedTail")}: {fmtPct(data.prediction?.omitted_mass, 2)}
                        </span>
                      </div>
                      <p className="text-[11px] text-gray-500 mb-3">{t("modal.matrixAxes")}</p>
                      {Array.isArray(data.prediction?.score_matrix) ? (
                        <div className="overflow-x-auto">
                          <table className="w-full text-center text-xs font-mono border-collapse">
                            <thead>
                              <tr>
                                <th className="p-1.5 text-gray-500 text-[10px]">H \ A</th>
                                {[0, 1, 2, 3, 4, 5].map((g) => (
                                  <th key={g} className="p-1.5 text-gray-400 font-bold">
                                    {g}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {data.prediction.score_matrix.map((row: unknown, hGoals: number) => (
                                <tr key={hGoals}>
                                  <td className="p-1.5 text-gray-400 font-bold">{hGoals}</td>
                                  {Array.isArray(row)
                                    ? row.map((prob: unknown, aGoals: number) => {
                                        const n = finiteNumber(prob);
                                        const opacity = n == null ? 0 : Math.min(1, Math.max(0, n * 6));
                                        return (
                                          <td
                                            key={aGoals}
                                            style={{ backgroundColor: `rgba(59, 130, 246, ${opacity * 0.4})` }}
                                            className="p-1.5 border border-gray-800/60 rounded text-[11px] font-medium text-gray-200"
                                          >
                                            {n == null ? "—" : `${(n * 100).toFixed(1)}%`}
                                          </td>
                                        );
                                      })
                                    : null}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                      )}
                    </div>
                    <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 flex flex-col justify-between">
                      <div>
                        <h4 className="text-sm font-bold text-white uppercase tracking-wider mb-4">{t("modal.topScores")}</h4>
                        <div className="space-y-3 font-mono">
                          {Array.isArray(data.prediction?.top_scores) ? (
                            data.prediction.top_scores.map((sc: any, idx: number) => (
                              <div
                                key={sc?.score ?? idx}
                                className="flex items-center justify-between p-3 bg-gray-900/60 border border-gray-800 rounded-lg"
                              >
                                <div className="flex items-center space-x-3">
                                  <span className="w-6 h-6 rounded-full bg-blue-600/20 text-blue-400 border border-blue-500/30 flex items-center justify-center font-bold text-xs">
                                    {idx + 1}
                                  </span>
                                  <span className="font-extrabold text-white text-base">{sc?.score ?? "—"}</span>
                                </div>
                                <span className="text-emerald-400 font-bold text-sm">{fmtPct(sc?.prob, 2)}</span>
                              </div>
                            ))
                          ) : (
                            <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                          )}
                        </div>
                      </div>
                      <div className="mt-4 pt-4 border-t border-gray-800 text-[11px] text-gray-500 font-mono">
                        <p>
                          {t("modal.trainingCutoff")}: {fmtUtc(data.prediction?.training_cutoff)}
                        </p>
                        <p>
                          {t("modal.decisionCutoff")}: {fmtUtc(data.prediction?.as_of)}
                        </p>
                      </div>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                )
              )}

              {activeTab === "STAKE" &&
                (outcomes.length > 0 ? (
                  <div className="bg-[#090d16] rounded-xl border border-gray-800 p-5 space-y-4">
                    <h4 className="text-sm font-bold text-white uppercase tracking-wider flex items-center">
                      <Calculator className="w-4 h-4 mr-1.5 text-emerald-400" /> {t("modal.kellyTitle")}
                    </h4>
                    <div className="bg-[#0f1523] border border-gray-800 p-4 rounded-xl flex items-center space-x-4">
                      <label className="text-xs font-mono text-gray-300" htmlFor="kelly-bankroll">
                        {t("modal.bankrollPrompt")}:
                      </label>
                      <input
                        id="kelly-bankroll"
                        type="number"
                        value={bankrollInput}
                        onChange={(e) => setBankrollInput(e.target.value)}
                        onBlur={commitBankroll}
                        className="w-32 px-3 py-1.5 bg-[#090d16] border border-gray-700 rounded-lg text-white font-mono text-sm font-bold focus:border-blue-500 focus:outline-none"
                      />
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 font-mono text-xs">
                      {outcomes.map((item: any, idx: number) => {
                        const ev = finiteNumber(item?.ev);
                        const half = finiteNumber(item?.half_kelly);
                        const stake = half != null && half > 0 ? bankroll * half : 0;
                        const profit = ev != null ? stake * ev : 0;
                        return (
                          <div
                            key={item?.outcome ?? idx}
                            className={`p-4 rounded-xl border ${
                              ev != null && ev >= 0.05
                                ? "bg-emerald-950/20 border-emerald-500/40"
                                : "bg-[#0f1523] border-gray-800"
                            }`}
                          >
                            <div className="flex justify-between items-center mb-2">
                              <span className="font-bold text-white text-base">{item?.outcome ?? "—"}</span>
                              <span className="text-gray-400">
                                {t("modal.oddsWord")}: {fmtFixed(item?.odds, 2)}
                              </span>
                            </div>
                            <div className="space-y-1.5 pt-2 border-t border-gray-800/80">
                              <div className="flex justify-between">
                                <span className="text-gray-400">{t("modal.halfKellyPct")}:</span>
                                <span className="font-bold text-white">
                                  {half == null ? "—" : `${(half * 100).toFixed(2)}%`}
                                </span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-400">{t("modal.suggestedStake")}:</span>
                                <span className="font-bold text-emerald-400 text-sm">${stake.toFixed(2)}</span>
                              </div>
                              <div className="flex justify-between">
                                <span className="text-gray-400">{t("modal.expectedProfit")}:</span>
                                <span className="font-bold text-blue-400">{fmtSignedMoney(profit)}</span>
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">{t("modal.noData")}</p>
                ))}
            </div>
          ) : null}
        </div>

        <div className="px-5 sm:px-7 py-3 border-t border-gray-800 bg-[#090d16] flex items-center justify-between flex-shrink-0 text-xs text-gray-500 font-mono">
          <span>{t("modal.escHint")}</span>
          <button
            type="button"
            onClick={() => onCloseRef.current()}
            className="px-4 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 font-semibold transition border border-gray-700 shadow-sm"
          >
            {t("modal.closeWindow")}
          </button>
        </div>
      </div>
    </div>
  );
};
