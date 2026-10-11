"use client";

import React, { useEffect, useRef, useState } from "react";
import { X, Check, Shield, ExternalLink, RefreshCw, AlertCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { lockBodyScroll } from "@/lib/scrollLock";
import { trapTabKey } from "@/lib/focusTrap";

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: any;
  onSuccessPayment: () => void;
}

const TERMINAL_STATUSES = ["PAID", "FAILED", "EXPIRED", "REVIEW"];
const POLL_LIMIT = 60;

function newIdempotencyKey(): string {
  const cryptoObj = typeof globalThis !== "undefined" ? globalThis.crypto : undefined;
  if (cryptoObj && typeof cryptoObj.randomUUID === "function") {
    return cryptoObj.randomUUID();
  }
  const bytes = new Uint8Array(16);
  if (cryptoObj && typeof cryptoObj.getRandomValues === "function") {
    cryptoObj.getRandomValues(bytes);
  } else {
    for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
  }
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export const PricingModal: React.FC<PricingModalProps> = ({
  isOpen,
  onClose,
  user,
  onSuccessPayment,
}) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  const [selectedPlan, setSelectedPlan] = useState<"PRO_DAY" | "PRO_WEEK" | "PRO_MONTHLY" | "PRO_SEASON">("PRO_MONTHLY");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeOrder, setActiveOrder] = useState<any | null>(null);
  const [pollingStatus, setPollingStatus] = useState<string | null>(null);
  const [dayPrice, setDayPrice] = useState<number | null>(null);
  const [weekPrice, setWeekPrice] = useState<number | null>(null);
  const [monthlyPrice, setMonthlyPrice] = useState<number | null>(null);
  const [seasonPrice, setSeasonPrice] = useState<number | null>(null);
  const [popupBlocked, setPopupBlocked] = useState(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const onSuccessRef = useRef(onSuccessPayment);
  onSuccessRef.current = onSuccessPayment;
  const activeOrderRef = useRef<any>(null);
  activeOrderRef.current = activeOrder;
  const dialogRef = useRef<HTMLDivElement>(null);
  const tRef = useRef(t);
  tRef.current = t;

  const orderId = activeOrder?.order_id ?? null;
  const orderStatus = activeOrder?.payment_status ?? null;

  useEffect(() => {
    if (!isOpen) return;
    let cancelled = false;
    apiRequest<{ day_price_usd: number; week_price_usd: number; monthly_price_usd: number; season_price_usd: number }>("/payments/pricing")
      .then((res) => {
        if (cancelled) return;
        const day = Number(res?.day_price_usd);
        const week = Number(res?.week_price_usd);
        const monthly = Number(res?.monthly_price_usd);
        const season = Number(res?.season_price_usd);
        setDayPrice(Number.isFinite(day) ? day : null);
        setWeekPrice(Number.isFinite(week) ? week : null);
        setMonthlyPrice(Number.isFinite(monthly) ? monthly : null);
        setSeasonPrice(Number.isFinite(season) ? season : null);
      })
      .catch(() => {
        // Checkout still uses the server price when the public quote is unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;
    const urlParams = new URLSearchParams(window.location.search);
    const urlOrderId = urlParams.get("order_id");
    const status = (urlParams.get("status") || "").toLowerCase();
    if (!urlOrderId) return;
    if (status !== "success" && status !== "pending") return;
    const prev = activeOrderRef.current;
    if (prev?.order_id === urlOrderId && TERMINAL_STATUSES.includes(prev.payment_status)) {
      return;
    }
    if (
      prev?.order_id === urlOrderId &&
      (prev.payment_status === "PENDING" || prev.payment_status === "CREATING")
    ) {
      return;
    }
    setActiveOrder({ order_id: urlOrderId, payment_status: "PENDING" });
    setPollingStatus("PENDING");
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !orderId) return;
    if (orderStatus !== "PENDING" && orderStatus !== "CREATING") return;

    let polls = 0;
    let stopped = false;
    const interval = setInterval(async () => {
      if (stopped) return;
      polls += 1;
      if (polls > POLL_LIMIT) {
        stopped = true;
        clearInterval(interval);
        return;
      }
      try {
        const res = await apiRequest<any>(`/payments/orders/${orderId}`);
        if (stopped) return;
        const status = res?.payment_status;
        setPollingStatus(status);
        // A successful refresh means the previous transient network error no
        // longer applies; clear the stale banner.
        setError(null);
        if (status === "PAID") {
          setActiveOrder(res);
          onSuccessRef.current();
          stopped = true;
          clearInterval(interval);
        } else if (status === "FAILED" || status === "EXPIRED" || status === "REVIEW") {
          setActiveOrder(res);
          stopped = true;
          clearInterval(interval);
        } else if (status) {
          setActiveOrder(res);
        }
      } catch (err: any) {
        if (stopped) return;
        const current = activeOrderRef.current;
        if (current?.payment_status === "PAID") return;
        setError(err?.message || tRef.current("pricing.pollError"));
      }
    }, 5000);

    return () => {
      stopped = true;
      clearInterval(interval);
    };
  }, [isOpen, orderId, orderStatus]);

  useEffect(() => {
    if (!isOpen) return;
    const release = lockBodyScroll();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
      if (e.key === "Tab") trapTabKey(e, dialogRef.current);
    };
    window.addEventListener("keydown", handleKeyDown);
    const focusId = window.setTimeout(() => {
      dialogRef.current?.querySelector<HTMLElement>("button, [href], input, select, textarea")?.focus();
    }, 0);
    return () => {
      release();
      window.removeEventListener("keydown", handleKeyDown);
      window.clearTimeout(focusId);
    };
  }, [isOpen]);

  const formatUsd = (value: number | null) => {
    if (value == null || !Number.isFinite(value)) return "—";
    const rounded = Math.round(value * 100) / 100;
    return Number.isInteger(rounded) ? `$${rounded}` : `$${rounded.toFixed(2)}`;
  };

  if (!isOpen) return null;

  const handleCheckout = async () => {
    if (!user) {
      setError(isEn ? "Please log in before purchasing a pass." : "请在购买通行证前先登录账号。");
      return;
    }
    setError(null);
    setPopupBlocked(false);
    const checkoutWindow = window.open("about:blank", "_blank");
    setLoading(true);

    try {
      const idempotencyKey = newIdempotencyKey();
      const res = await apiRequest<any>("/payments/create-invoice", {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ plan_type: selectedPlan }),
      });

      setActiveOrder(res);
      setPollingStatus(res.payment_status);

      if (res.checkout_url && checkoutWindow && !checkoutWindow.closed) {
        checkoutWindow.location.href = res.checkout_url;
      } else {
        if (checkoutWindow && !checkoutWindow.closed) checkoutWindow.close();
        setPopupBlocked(true);
      }
    } catch (err: any) {
      if (checkoutWindow && !checkoutWindow.closed) checkoutWindow.close();
      setError(err?.message || (isEn ? "Failed to initialize payment invoice." : "生成支付账单失败，请重试。"));
    } finally {
      setLoading(false);
    }
  };

  const status = activeOrder?.payment_status;
  const isTerminal = TERMINAL_STATUSES.includes(status);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCloseRef.current();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="pricing-dialog-title"
        className="bg-[#101625] border border-gray-800 rounded-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto p-6 sm:p-8 relative shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={() => onCloseRef.current()}
          className="absolute top-5 right-5 text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition"
          aria-label={t("modal.close")}
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center max-w-md mx-auto mb-8">
          <div className="inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
            <Shield className="w-3.5 h-3.5 mr-1" /> {isEn ? "MatchLambda Analyst Pass" : "MatchLambda 专家专属通行证"}
          </div>
          <h2 id="pricing-dialog-title" className="text-2xl font-extrabold text-white">
            {t("pricing.title")}
          </h2>
          <p className="text-xs text-gray-400 mt-2">{t("pricing.subtitle")}</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center text-xs text-red-400">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="mb-6 p-3.5 bg-slate-900/80 border border-gray-800 rounded-xl">
          <p className="text-[11px] text-gray-300 leading-relaxed">
            <strong className="text-gray-400">{t("disclaimer.title")}</strong>
            {t("pricing.disclaimer")}
          </p>
        </div>

        {!activeOrder ? (
          <div>
            {/* Entry-level quick passes */}
            <div className="grid grid-cols-2 gap-4 mb-4">
              <div
                onClick={() => setSelectedPlan("PRO_DAY")}
                className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                  selectedPlan === "PRO_DAY"
                    ? "bg-emerald-600/10 border-emerald-500"
                    : "bg-[#0b0f1a] border-gray-800 hover:border-gray-700"
                }`}
              >
                <div>
                  <h4 className="font-bold text-white text-sm">{isEn ? "Day Pass" : "单日通行证"}</h4>
                  <p className="text-[10px] text-gray-400 mt-0.5">{isEn ? "24h full access" : "24 小时完整权限"}</p>
                </div>
                <span className="text-lg font-extrabold text-emerald-400">{formatUsd(dayPrice)}</span>
              </div>
              <div
                onClick={() => setSelectedPlan("PRO_WEEK")}
                className={`p-3.5 rounded-xl border cursor-pointer transition flex items-center justify-between ${
                  selectedPlan === "PRO_WEEK"
                    ? "bg-emerald-600/10 border-emerald-500"
                    : "bg-[#0b0f1a] border-gray-800 hover:border-gray-700"
                }`}
              >
                <div>
                  <h4 className="font-bold text-white text-sm">{isEn ? "Week Pass" : "周通行证"}</h4>
                  <p className="text-[10px] text-gray-400 mt-0.5">{isEn ? "7 days, one match week" : "7 天，覆盖一个比赛周"}</p>
                </div>
                <span className="text-lg font-extrabold text-emerald-400">{formatUsd(weekPrice)}</span>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div
                onClick={() => setSelectedPlan("PRO_MONTHLY")}
                className={`p-5 rounded-xl border cursor-pointer transition relative ${
                  selectedPlan === "PRO_MONTHLY"
                    ? "bg-blue-600/10 border-blue-500 shadow-lg shadow-blue-500/10"
                    : "bg-[#0b0f1a] border-gray-800 hover:border-gray-700"
                }`}
              >
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-bold text-white text-base">{isEn ? "Monthly Pass" : "月度通行证"}</h4>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                    {isEn ? "30 Days" : "30 天"}
                  </span>
                </div>
                <div className="flex items-baseline mb-4">
                  <span className="text-3xl font-extrabold text-white">{formatUsd(monthlyPrice)}</span>
                  <span className="text-xs text-gray-400 ml-1">{isEn ? "/ one-time" : "/ 一次性"}</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "Dixon-Coles 1X2 probability estimates" : "已支持赛事的 Dixon-Coles 1X2 概率估计"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "6×6 Score Distribution Matrix" : "6×6 详尽比分联合概率矩阵"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" />{" "}
                    {isEn
                      ? "Latest eligible +EV scanner signals and Kelly sizing"
                      : "通过时效校验的 +EV 信号与凯利仓位计算"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "Multi-market Derivatives: Totals & BTTS" : "高阶衍生盘口：大小球、双进与亚盘让球"}
                  </li>
                </ul>
              </div>

              <div
                onClick={() => setSelectedPlan("PRO_SEASON")}
                className={`p-5 rounded-xl border cursor-pointer transition relative ${
                  selectedPlan === "PRO_SEASON"
                    ? "bg-blue-600/10 border-blue-500 shadow-lg shadow-blue-500/10"
                    : "bg-[#0b0f1a] border-gray-800 hover:border-gray-700"
                }`}
              >
                <div className="absolute -top-3 right-4 bg-gradient-to-r from-amber-500 to-orange-500 text-black font-extrabold text-[10px] px-2 py-0.5 rounded-full uppercase tracking-wider">
                  {isEn ? "Best Value" : "推荐首选"}
                </div>
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-bold text-white text-base">{isEn ? "Season Pass" : "赛季通行证"}</h4>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                    {isEn ? "270 Days" : "270 天"}
                  </span>
                </div>
                <div className="flex items-baseline mb-4">
                  <span className="text-3xl font-extrabold text-white">{formatUsd(seasonPrice)}</span>
                  <span className="text-xs text-gray-400 ml-1">{isEn ? "/ one-time" : "/ 一次性"}</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" />{" "}
                    {isEn
                      ? "Analyst features across supported leagues for 270 days"
                      : "已支持联赛的 Analyst 功能，有效期 270 天"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "Eligible +EV scanner with a 5% minimum EV" : "最低 5% EV 的有效信号与仓位计算"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "Smart Parlay 2-fold & 3-fold Generator" : "智能 2 串 1 / 3 串 1 方案一键生成"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" />{" "}
                    {isEn ? "Hypothetical Monte Carlo scenarios" : "基于输入假设的蒙特卡洛情景模拟"}
                  </li>
                </ul>
              </div>
            </div>

            <button
              onClick={handleCheckout}
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-3 rounded-xl text-sm transition shadow-lg shadow-blue-600/25 flex items-center justify-center disabled:opacity-50"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                  {isEn ? "Creating Secure Hosted Invoice..." : "正在创建加密货币收银台账单..."}
                </>
              ) : (
                <>
                  {t("pricing.payCrypto")}
                  <ExternalLink className="w-4 h-4 ml-2" />
                </>
              )}
            </button>
          </div>
        ) : (
          <div className="p-6 bg-[#0b0f1a] border border-gray-800 rounded-xl text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 flex items-center justify-center mx-auto">
              {status === "PAID" ? (
                <Check className="w-6 h-6 text-emerald-400" />
              ) : isTerminal ? (
                <AlertCircle className="w-6 h-6 text-amber-400" />
              ) : (
                <RefreshCw className="w-6 h-6 animate-spin" />
              )}
            </div>

            <div>
              <h4 className="font-bold text-white text-lg">
                {status === "PAID"
                  ? isEn
                    ? "Payment Confirmed & Pass Activated!"
                    : "支付成功，ANALYST 权限已即时开通！"
                  : isTerminal
                    ? status
                    : isEn
                      ? "Awaiting Crypto Settlement"
                      : "等待链上确认结算中..."}
              </h4>
              <p className="text-xs text-gray-400 mt-1 font-mono">Order ID: {activeOrder.order_id}</p>
            </div>

            <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
              <span className="text-gray-400">{isEn ? "Status:" : "状态:"}</span>
              <span className="font-bold font-mono text-blue-400">{pollingStatus || status}</span>
            </div>

            {popupBlocked && activeOrder.checkout_url && (
              <p className="text-xs text-amber-300">{t("pricing.popupBlocked")}</p>
            )}

            {activeOrder.checkout_url && status !== "PAID" && (
              <div className="pt-2">
                <a
                  href={activeOrder.checkout_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white px-4 py-2.5 rounded-lg transition"
                >
                  {isEn ? "Open NOWPayments Hosted Checkout" : "前往 NOWPayments 安全收银台支付"}{" "}
                  <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                </a>
              </div>
            )}

            {status === "PAID" && (
              <div className="pt-2">
                <button
                  onClick={() => onCloseRef.current()}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-5 py-2.5 rounded-lg transition"
                >
                  {isEn ? "Start Analyzing Matches" : "立即体验量化终端"}
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
