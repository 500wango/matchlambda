"use client";

import React, { useState, useEffect } from "react";
import { X, Check, Shield, ExternalLink, RefreshCw, AlertCircle } from "lucide-react";
import { apiRequest } from "@/lib/api";

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
      setError("Please log in before purchasing a pass.");
      return;
    }
    setError(null);
    setLoading(true);

    try {
      // Generate standard UUID v4 idempotency key
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
      setError(err?.message || "Failed to initialize payment invoice.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm">
      <div className="bg-[#101625] border border-gray-800 rounded-2xl w-full max-w-2xl p-6 sm:p-8 relative shadow-2xl">
        <button
          onClick={onClose}
          className="absolute top-5 right-5 text-gray-400 hover:text-white p-1 rounded-lg"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="text-center max-w-md mx-auto mb-8">
          <div className="inline-flex items-center space-x-1 px-3 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-3">
            <Shield className="w-3.5 h-3.5 mr-1" /> MatchLambda Analyst Pass
          </div>
          <h2 className="text-2xl font-extrabold text-white">Full Access to EPL Probabilities</h2>
          <p className="text-xs text-gray-400 mt-2">
            Non-recurring passes with instant cryptocurrency checkout via NOWPayments.
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
                  <h4 className="font-bold text-white text-base">Monthly Pass</h4>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-blue-500/20 text-blue-400">
                    30 Days
                  </span>
                </div>
                <div className="flex items-baseline mb-4">
                  <span className="text-3xl font-extrabold text-white">$29</span>
                  <span className="text-xs text-gray-400 ml-1">/ one-time</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> Full Dixon-Coles 1X2 Probabilities
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> 6×6 Score Distribution Matrix
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> Real-time EV & Half-Kelly Scanner
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-blue-400 mr-2 flex-shrink-0" /> Shin De-juiced Market Benchmarks
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
                  Best Value
                </div>
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-bold text-white text-base">Season Pass</h4>
                  <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-500/20 text-amber-400">
                    270 Days
                  </span>
                </div>
                <div className="flex items-baseline mb-4">
                  <span className="text-3xl font-extrabold text-white">$149</span>
                  <span className="text-xs text-gray-400 ml-1">/ 9 months</span>
                </div>
                <ul className="space-y-2 text-xs text-gray-300">
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> Full EPL Season Coverage (270d)
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> All Match Matrix & Top Scores
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> Unrestricted EV Filter & Alerts
                  </li>
                  <li className="flex items-center">
                    <Check className="w-3.5 h-3.5 text-amber-400 mr-2 flex-shrink-0" /> Complete Chronological Evaluation
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
                  Creating Secure Hosted Invoice...
                </>
              ) : (
                <>
                  Proceed with Crypto Checkout
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
                  ? "Payment Confirmed & Pass Activated!"
                  : "Awaiting Crypto Settlement"}
              </h4>
              <p className="text-xs text-gray-400 mt-1 font-mono">Order ID: {activeOrder.order_id}</p>
            </div>

            <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-gray-900 border border-gray-800 text-xs">
              <span className="text-gray-400">Status:</span>
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
                  Open NOWPayments Checkout <ExternalLink className="w-3.5 h-3.5 ml-1.5" />
                </a>
              </div>
            )}

            {activeOrder.payment_status === "PAID" && (
              <div className="pt-2">
                <button
                  onClick={onClose}
                  className="bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs px-5 py-2.5 rounded-lg transition"
                >
                  Start Analyzing EPL Matches
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
