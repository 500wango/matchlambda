"use client";

import React, { useEffect, useRef, useState } from "react";
import { X, Lock, Mail, AlertCircle } from "lucide-react";
import { apiRequest, setAuthToken } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { lockBodyScroll } from "@/lib/scrollLock";
import { trapTabKey } from "@/lib/focusTrap";

interface AuthModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const AuthModal: React.FC<AuthModalProps> = ({ isOpen, onClose, onSuccess }) => {
  if (!isOpen) return null;
  return <AuthDialog onClose={onClose} onSuccess={onSuccess} />;
};

const AuthDialog: React.FC<Omit<AuthModalProps, "isOpen">> = ({ onClose, onSuccess }) => {
  const { lang, t } = useI18n();
  const isEn = lang === "en";
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const dialogRef = useRef<HTMLDivElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const release = lockBodyScroll();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onCloseRef.current();
      if (e.key === "Tab") trapTabKey(e, dialogRef.current);
    };
    window.addEventListener("keydown", handleKeyDown);
    const focusId = window.setTimeout(() => emailRef.current?.focus(), 0);
    return () => {
      release();
      window.removeEventListener("keydown", handleKeyDown);
      window.clearTimeout(focusId);
    };
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    let registered = false;

    try {
      if (isRegister) {
        if (password.length < 12 || password.length > 128) {
          throw new Error(
            isEn
              ? "Password must be between 12 and 128 characters."
              : "密码长度必须在 12 到 128 个字符之间。"
          );
        }
        await apiRequest("/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        registered = true;
      }

      const res = await apiRequest<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });

      setAuthToken(res.access_token);
      onSuccess();
      onCloseRef.current();
    } catch (err: any) {
      if (registered) {
        setIsRegister(false);
        setError(
          isEn
            ? "Account created, but sign-in failed. Please sign in."
            : "账号已创建，但登录失败。请使用该账号登录。"
        );
      } else {
        setError(err?.message || (isEn ? "Authentication failed." : "认证失败，请检查账号密码。"));
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCloseRef.current();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="auth-dialog-title"
        className="bg-[#111726] border border-gray-800 rounded-2xl w-full max-w-md p-6 relative shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          onClick={() => onCloseRef.current()}
          className="absolute top-4 right-4 text-gray-400 hover:text-white p-1 rounded-lg hover:bg-gray-800 transition"
          aria-label={t("modal.close")}
        >
          <X className="w-5 h-5" />
        </button>

        <h3 id="auth-dialog-title" className="text-xl font-bold text-white mb-1">
          {isRegister ? t("auth.registerTitle") : t("auth.loginTitle")}
        </h3>
        <p className="text-xs text-gray-400 mb-6">
          {isRegister
            ? isEn
              ? "Sign up to access Poisson probabilities and smart picks."
              : "注册开启五大联赛与全球赛事泊松模型及每日智能推荐。"
            : isEn
              ? "Log in with your registered email to continue."
              : "使用您注册的邮箱登录以继续使用。"}
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center text-xs text-red-400">
            <AlertCircle className="w-4 h-4 mr-2 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5" htmlFor="auth-email">
              {t("auth.email")}
            </label>
            <div className="relative">
              <Mail className="w-4 h-4 absolute left-3 top-3 text-gray-500" />
              <input
                id="auth-email"
                ref={emailRef}
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="analyst@example.com"
                autoComplete="email"
                className="w-full bg-[#0a0f1d] border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1.5" htmlFor="auth-password">
              {t("auth.password")}{" "}
              {isRegister && (
                <span className="text-gray-400 font-normal">
                  ({isEn ? "min 12 chars" : "至少 12 个字符"})
                </span>
              )}
            </label>
            <div className="relative">
              <Lock className="w-4 h-4 absolute left-3 top-3 text-gray-500" />
              <input
                id="auth-password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                autoComplete={isRegister ? "new-password" : "current-password"}
                className="w-full bg-[#0a0f1d] border border-gray-700 rounded-lg pl-9 pr-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium py-2.5 rounded-lg text-sm transition shadow-lg shadow-blue-600/25 disabled:opacity-50 mt-2"
          >
            {loading
              ? isEn
                ? "Processing..."
                : "处理中..."
              : isRegister
                ? t("auth.registerSubmit")
                : t("auth.loginSubmit")}
          </button>
        </form>

        <div className="mt-5 text-center text-xs text-gray-400">
          {isRegister ? (
            <button
              type="button"
              onClick={() => {
                setIsRegister(false);
                setError(null);
              }}
              className="text-blue-400 hover:underline font-medium"
            >
              {t("auth.hasAccount")}
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                setIsRegister(true);
                setError(null);
              }}
              className="text-blue-400 hover:underline font-medium"
            >
              {t("auth.needAccount")}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
