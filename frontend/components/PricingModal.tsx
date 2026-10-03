"use client";

import React, { useState, useEffect } from "react";
import { X, Check, Shield, ExternalLink, RefreshCw, AlertCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface PricingModalProps {
  isOpen: boolean;
  onClose: () => void;
  user: any;
  onSuccessPayment: () => void;
}

export const PricingModal: React.FC<PricingModalProps> = ({
  isOpen,
  onClose,
  user,
  onSuccessPayment,
}) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  const [selectedPlan, setSelectedPlan] = useState<"PRO_MONTHLY" | "PRO_SEASON">("PRO_MONTHLY");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeOrder, setActiveOrder] = useState<any | null>(null);
  const [pollingStatus, setPollingStatus] = useState<string | null>(null);

  // Check URL on open
  useEffect(() => {
    if (typeof window !== "undefined") {
      const urlParams = new URLSearchParams(window.location.search);
      const orderId = urlParams.get("order_id");
      if (orderId && !activeOrder) {
        setActiveOrder({ order_id: orderId, payment_status: "PENDING" });
        setPollingStatus("PENDING");
      }
    }
  }, [isOpen]);

  // Poll order status
  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;

    if (activeOrder && (activeOrder.payment_status === "PENDING" || activeOrder.payment_status === "CREATING")) {
      interval = setInterval(async () => {
        try {
          const res = await apiRequest<any>(`/payments/orders/${activeOrder.order_id}`);
          setPollingStatus(res.payment_status);
          if (res.payment_status === "PAID") {
            setActiveOrder(res);
            onSuccessPayment();
            if (interval) clearInterval(interval);
          } else if (res.payment_status === "FAILED" || res.payment_status === "EXPIRED" || res.payment_status === "REVIEW") {
            setActiveOrder(res);
            if (interval) clearInterval(interval);
          }
        } catch (e) {
          // Keep silent on transient polling errors
        }
      }, 5000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeOrder, onSuccessPayment]);

  if (!isOpen) return null;

  const handleCheckout = async () => {
    if (!user) {
      setError(isEn ? "Please log in before purchasing a pass." : "请在购买通行证前先登录账号。");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const idempotencyKey = crypto.randomUUID();

      const res = await apiRequest<any>("/payments/create-invoice", {
        method: "POST",
        headers: {
          "Idempotency-Key": idempotencyKey,
        },
        body: JSON.stringify({ plan_type: selectedPlan }),
      });

      setActiveOrder(res);
      setPollingStatus(res.payment_status);

      if (res.checkout_url) {
        window.open(res.checkout_url, "_blank", "noopener,noreferrer");
      }
    } catch (err: any) {
      setError(err?.message || (isEn ? "Failed to initialize payment invoice." : "生成支付账单失败，请重试。"));
    } finally {
      setLoading(false);
    }
  };

  // Esc key listener
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-[#101625] border border-gray-800 rounded-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto p-6 sm:p-8 relative shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-5 right-5 text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition"
          aria-label={isEn ? "Close" : "关闭"}
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center max-w-md mx-auto mb-8">
          <div className="inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
            <Shield className="w-3.5 h-3.5 mr-1" /> {isEn ? "MatchLambda Analyst Pass" : "MatchLambda 专家专属通行证"}
          </div>
          <h2 className="text-2xl font-extrabold text-white">{t("pricing.title")}</h2>
          <p className="text-xs text-gray-400 mt-2">
            {t("pricing.subtitle")}
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center text-xs text-red-400">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!activeOrder ? (
          <div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              {/* Pro Monthly */}
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
                  <span className="text-3xl font-extrabold text-white">$29</span>
                  <span className="text-xs text-gray-400 ml-1">{isEn ? "/ one-time" : "/ 一次性"}</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> {isEn ? "Full Dixon-Coles 1X2 Probabilities" : "五大联赛与全球联赛 1X2 泊松真实概率"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> {isEn ? "6×6 Score Distribution Matrix" : "6×6 详尽比分联合概率矩阵"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> {isEn ? "Real-time +EV Alpha Scanner" : "实时 +EV 价值雷达与凯利仓位计算"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> {isEn ? "Multi-market Derivatives: Totals & BTTS" : "高阶衍生盘口：大小球、双进与亚盘让球"}
                  </li>
                </ul>
              </div>

              {/* Pro Season */}
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
                  <h4 className="font-bold text-white text-base">{isEn ? "Season Pass" : "季度赛季通行证"}</h4>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                    {isEn ? "90 Days" : "90 天"}
                  </span>
                </div>
                <div className="flex items-baseline mb-4">
                  <span className="text-3xl font-extrabold text-white">$69</span>
                  <span className="text-xs text-gray-400 ml-1">{isEn ? "/ 3 months" : "/ 3 个月"}</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> {isEn ? "All 17 Leagues Full Coverage (90d)" : "全部 17 大联赛无限覆盖 (90天)"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> {isEn ? "Unrestricted +EV Scanner & Staking" : "无限制实时 +EV 信号雷达与实时推送"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> {isEn ? "Smart Parlay 2-fold & 3-fold Generator" : "智能 2 串 1 / 3 串 1 方案一键生成"}
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> {isEn ? "Monte Carlo Bankroll Simulation" : "蒙特卡洛 1000 路径资金回撤模拟"}
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
              {activeOrder.payment_status === "PAID" ? (
                <Check className="w-6 h-6 text-emerald-400" />
              ) : (
                <RefreshCw className="w-6 h-6 animate-spin" />
              )}
            </div>

            <div>
              <h4 className="font-bold text-white text-lg">
                {activeOrder.payment_status === "PAID"
                  ? (isEn ? "Payment Confirmed & Pass Activated!" : "支付成功，ANALYST 权限已即时开通！")
                  : (isEn ? "Awaiting Crypto Settlement" : "等待链上确认结算中...")}
              </h4>
              <p className="text-xs text-gray-400 mt-1 font-mono">Order ID: {activeOrder.order_id}</p>
            </div>

            <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
              <span className="text-gray-400">{isEn ? "Status:" : "状态:"}</span>
              <span className="font-bold font-mono text-blue-400">{pollingStatus || activeOrder.payment_status}</span>
            </div>

            {activeOrder.checkout_url && activeOrder.payment_status !== "PAID" && (
              <div className="pt-2">
                <a
                  href={activeOrder.checkout_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white px-4 py-2.5 rounded-lg transition"
                >
                  {isEn ? "Open NOWPayments Hosted Checkout" : "前往 NOWPayments 安全收银台支付"} <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                </a>
              </div>
            )}

            {activeOrder.payment_status === "PAID" && (
              <div className="pt-2">
                <button
                  onClick={onClose}
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
