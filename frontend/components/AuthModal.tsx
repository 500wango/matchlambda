"use client";

import React, { useState, useEffect } from "react";
import { X, Lock, Mail, AlertCircle } from "lucide-react";
import { apiRequest, setAuthToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Esc key listener
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (isRegister) {
        if (password.length < 12 || password.length > 128) {
          throw { message: isEn ? "Password must be between 12 and 128 characters." : "密码长度必须在 12 到 128 个字符之间。" };
        }
        await apiRequest("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }

      // Login to obtain token
      const res = await apiRequest<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      setAuthToken(res.access_token);
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err?.message || (isEn ? "Authentication failed." : "认证失败，请检查账号密码。"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="bg-[#111726] border border-gray-800 rounded-2xl w-full max-w-md p-6 relative shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition"
          aria-label={isEn ? "Close" : "关闭"}
        >
          <X className="w-5 h-5" />
        </button>

        <h3 className="text-xl font-bold text-white mb-1">
          {isRegister ? t("auth.registerTitle") : t("auth.loginTitle")}
        </h3>
        <p className="text-xs text-gray-400 mb-6">
          {isRegister
            ? (isEn ? "Sign up to access Poisson probabilities and smart picks." : "注册开启五大联赛与全球赛事泊松模型及每日智能推荐。")
            : (isEn ? "Log in with your registered email to continue." : "使用您注册的邮箱登录以继续使用。")}
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center text-xs text-red-400">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">{t("auth.email")}</label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-3 text-gray-500" />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@example.com"
                className="w-full bg-[#0a0f1d] border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5">
              {t("auth.password")} {isRegister && <span className="text-gray-400 font-normal">({isEn ? "min 12 chars" : "至少 12 个字符"})</span>}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-3 text-gray-500" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-[#0a0f1d] border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg text-sm transition shadow-lg shadow-blue-600/25 disabled:opacity-50 mt-2"
          >
            {loading ? (isEn ? "Processing..." : "处理中...") : isRegister ? t("auth.registerSubmit") : t("auth.loginSubmit")}
          </button>
        </form>

        <div className="mt-5 text-center text-xs text-gray-400">
          {isRegister ? (
            <>
              {isEn ? "Already have an account? " : "已有账号？ "}
              <button
                onClick={() => {
                  setIsRegister(false);
                  setError(null);
                }}
                className="text-blue-400 hover:underline font-medium"
              >
                {t("auth.hasAccount")}
              </button>
            </>
          ) : (
            <>
              {isEn ? "Don't have an account? " : "还没有账号？ "}
              <button
                onClick={() => {
                  setIsRegister(true);
                  setError(null);
                }}
                className="text-blue-400 hover:underline font-medium"
              >
                {t("auth.needAccount")}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
