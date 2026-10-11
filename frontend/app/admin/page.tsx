"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  Shield,
  Database,
  Brain,
  CreditCard,
  Upload,
  RefreshCw,
  CheckCircle2,
  AlertTriangle,
  ArrowLeft,
  ChevronRight,
  TrendingUp,
  Award,
  Zap,
  Clock,
  Search,
  ExternalLink,
  Users,
  FileText,
  Lock,
  KeyRound,
  Settings,
  Plus,
  Trash2,
  Power,
  Globe2,
  Info,
  Sliders,
  Bell,
  Send,
  Coins,
  Activity,
  Check,
  Link2,
  Radio,
} from "lucide-react";
import { apiRequest, getAuthToken } from "@/lib/api";
import { useDebounced } from "@/lib/useDebounced";
import { AuthModal } from "@/components/AuthModal";
import { CustomSelect } from "@/components/CustomSelect";

type AdminTab = "data_etl" | "model_ops" | "billing_users" | "settings";
type SettingsSubTab =
  | "leagues"
  | "aliases"
  | "quant_risk"
  | "provider"
  | "monetization"
  | "notifications"
  | "audit_cache";

interface SeasonOption {
  code: string;
  label: string;
  isCurrent?: boolean;
}

const REMOTE_LEAGUE_OPTIONS = [
  { value: "E0", label: "英超 (Premier League - E0)" },
  { value: "E1", label: "英冠 (Championship - E1)" },
  { value: "SP1", label: "西甲 (La Liga - SP1)" },
  { value: "I1", label: "意甲 (Serie A - I1)" },
  { value: "D1", label: "德甲 (Bundesliga - D1)" },
  { value: "F1", label: "法甲 (Ligue 1 - F1)" },
  { value: "N1", label: "荷甲 (Eredivisie - N1)" },
  { value: "P1", label: "葡超 (Primeira Liga - P1)" },
  { value: "B1", label: "比甲 (Belgian Pro League - B1)" },
  { value: "AUT", label: "奥甲 (Austrian Bundesliga - AUT)" },
  { value: "SWE", label: "瑞超 (Allsvenskan - SWE)" },
  { value: "NOR", label: "挪超 (Eliteserien - NOR)" },
  { value: "DNK", label: "丹麦超 (Superliga - DNK)" },
];

const AVAILABLE_SEASONS: SeasonOption[] = [
  { code: "2627", label: "2026-2027 (当前进行中赛季)", isCurrent: true },
  { code: "2526", label: "2025-2026 (上赛季)" },
  { code: "2425", label: "2024-2025" },
  { code: "2324", label: "2023-2024" },
  { code: "2223", label: "2022-2023" },
  { code: "2122", label: "2021-2022" },
  { code: "2021", label: "2020-2021" },
  { code: "1920", label: "2019-2020" },
  { code: "1819", label: "2018-2019" },
  { code: "1718", label: "2017-2018" },
  { code: "1617", label: "2016-2017" },
  { code: "1516", label: "2015-2016" },
  { code: "1415", label: "2014-2015" },
];

const LEAGUE_ZH_NAMES: Record<string, string> = {
  EPL: "英超",
  CHAMPIONSHIP: "英冠",
  LA_LIGA: "西甲",
  SERIE_A: "意甲",
  BUNDESLIGA: "德甲",
  LIGUE_1: "法甲",
  EREDIVISIE: "荷甲",
  PRIMEIRA_LIGA: "葡超",
  ALLSVENSKAN: "瑞超",
  ELITESERIEN: "挪超",
  SUPERLIGA: "丹麦超",
  AUSTRIAN_BUNDESLIGA: "奥甲",
  MLS: "美职联",
  BRASILEIRAO: "巴西甲",
  SAUDI_PRO_LEAGUE: "沙特联",
  UCL: "欧冠",
  UEL: "欧联",
};

function formatLeagueLabel(id: string, name?: string): string {
  const zh = LEAGUE_ZH_NAMES[id] || "";
  const baseName = name || id;
  if (zh) {
    return `${zh} · ${baseName} (${id})`;
  }
  return `${baseName} (${id})`;
}

// NOTE: the former `formatDateSlice` / `blankMaskedSecrets` helpers were dead
// code and have been removed. `blankMaskedSecrets` was intended to strip
// masked secrets before PUT, but the backend already guarantees safety:
// - GET /admin/settings/config/data-provider returns `the_odds_api_key: ""`
//   plus a separate `the_odds_api_key_masked` (same for the notifications
//   token/webhook), so a masked value never lands in the editable field;
// - PUT ignores blanks and any value containing "****" and keeps the stored
//   secret (see backend/app/api/v1/admin/settings.py update handlers).
// Re-adding a client-side stripper would be redundant and risks blanking a
// real key if the field contract ever changes.

export default function AdminPage() {
  const [user, setUser] = useState<any>(null);
  const [loadingUser, setLoadingUser] = useState(true);
  const [activeTab, setActiveTab] = useState<AdminTab>("data_etl");
  const [toast, setToast] = useState<{ type: "success" | "error" | "info"; message: string } | null>(null);

  // ETL State
  const [leagues, setLeagues] = useState<any[]>([]);
  const [teams, setTeams] = useState<any[]>([]);
  const [loadingLeagues, setLoadingLeagues] = useState(false);

  // Remote Sync State
  const [remoteLeagueCode, setRemoteLeagueCode] = useState("E0");
  const [remoteSeason, setRemoteSeason] = useState("2627");
  const [remoteAutoTrain, setRemoteAutoTrain] = useState(true);
  const [syncingRemote, setSyncingRemote] = useState(false);
  const [syncResult, setSyncResult] = useState<any>(null);

  // CSV Preview & Commit State
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [previewLeagueId, setPreviewLeagueId] = useState("EPL");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any>(null);
  const [aliasMappings, setAliasMappings] = useState<Record<string, string>>({});
  const [committingCsv, setCommittingCsv] = useState(false);
  const [commitResult, setCommitResult] = useState<any>(null);

  // Model Ops State
  const [modelOverview, setModelOverview] = useState<any[]>([]);
  const [selectedModelLeague, setSelectedModelLeague] = useState("EPL");
  const [loadingModel, setLoadingModel] = useState(false);
  const [retrainingModel, setRetrainingModel] = useState(false);

  // Billing & Users State
  const [invoices, setInvoices] = useState<any[]>([]);
  const [usersList, setUsersList] = useState<any[]>([]);
  const [loadingBilling, setLoadingBilling] = useState(false);
  const [grantingOrderId, setGrantingOrderId] = useState<string | null>(null);
  const [isAuthOpen, setIsAuthOpen] = useState(false);

  // Settings State
  const [settingsSubTab, setSettingsSubTab] = useState<SettingsSubTab>("leagues");
  const [settingsLeagues, setSettingsLeagues] = useState<any[]>([]);
  const [systemInfo, setSystemInfo] = useState<any>(null);
  const [loadingSettings, setLoadingSettings] = useState(false);
  const [showAddLeague, setShowAddLeague] = useState(false);
  const [newLeagueId, setNewLeagueId] = useState("");
  const [newLeagueName, setNewLeagueName] = useState("");
  const [newLeagueCountry, setNewLeagueCountry] = useState("");
  const [newLeagueActive, setNewLeagueActive] = useState(true);
  const [creatingLeague, setCreatingLeague] = useState(false);
  const [leagueSearchQuery, setLeagueSearchQuery] = useState("");

  // New Team State
  const [showAddTeam, setShowAddTeam] = useState(false);
  const [newTeamId, setNewTeamId] = useState("");
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamCountry, setNewTeamCountry] = useState("");
  const [creatingTeam, setCreatingTeam] = useState(false);

  // Aliases State
  const [aliasesList, setAliasesList] = useState<any[]>([]);
  const [aliasSearch, setAliasSearch] = useState("");
  const debouncedAliasSearch = useDebounced(aliasSearch, 400);
  const [loadingAliases, setLoadingAliases] = useState(false);
  const [showAddAlias, setShowAddAlias] = useState(false);
  const [newAliasTeamId, setNewAliasTeamId] = useState("");
  const [newAliasName, setNewAliasName] = useState("");
  const [creatingAlias, setCreatingAlias] = useState(false);

  // Quant Risk State
  const [quantConfig, setQuantConfig] = useState<any>({
    value_scanner_min_ev: 0.05,
    kelly_fraction: 0.5,
    max_stake_cap: 0.05,
    dixon_coles_decay_xi: 0.0018,
    min_training_matches: 60,
  });
  const [savingQuant, setSavingQuant] = useState(false);

  // Provider & Quota State
  const [providerConfig, setProviderConfig] = useState<any>({
    the_odds_api_key: "",
    sharp_bookmakers: ["pinnacle", "betfair_ex_uk", "bet365", "williamhill"],
    polling_interval_hours: 4,
    live_monitoring_enabled: true,
  });
  const [quotaStatus, setQuotaStatus] = useState<any>(null);
  const [checkingQuota, setCheckingQuota] = useState(false);
  const [savingProvider, setSavingProvider] = useState(false);

  // Monetization State
  const [monetizationConfig, setMonetizationConfig] = useState<any>({
    monthly_price_usd: 29.0,
    season_price_usd: 149.0,
    new_user_trial_days: 3,
    accepted_tokens: ["USDTTRC20", "USDTERC20", "USDC", "BTC"],
  });
  const [savingMonetization, setSavingMonetization] = useState(false);

  // Notifications State
  const [notifConfig, setNotifConfig] = useState<any>({
    telegram_enabled: false,
    telegram_bot_token: "",
    telegram_channel_id: "",
    telegram_min_ev: 0.08,
    webhook_url: "",
    webhook_enabled: false,
  });
  const [savingNotif, setSavingNotif] = useState(false);
  const [testingNotif, setTestingNotif] = useState(false);
  const [testNotifResult, setTestNotifResult] = useState<any>(null);

  // Cache & Audit State
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);
  const [purgingCache, setPurgingCache] = useState(false);

  const toastTimerRef = useRef<number | null>(null);
  const showToast = (type: "success" | "error" | "info", message: string) => {
    if (toastTimerRef.current != null) clearTimeout(toastTimerRef.current);
    setToast({ type, message });
    toastTimerRef.current = window.setTimeout(() => setToast(null), 5000);
  };

  useEffect(() => {
    return () => {
      if (toastTimerRef.current != null) clearTimeout(toastTimerRef.current);
    };
  }, []);

  const safeSlice = (val: any, start: number, end: number, fallback = "—") => {
    return typeof val === "string" ? val.slice(start, end) : fallback;
  };

  // --- Request cancellation registry ---------------------------------------
  // Every admin data fetch runs through startFetch(): a newer request for the
  // same key aborts the previous one, and the sequence guard drops late
  // responses so a fast tab switch / search keystroke cannot clobber fresh data.
  const fetchAbortRef = useRef<Record<string, AbortController>>({});
  const fetchSeqRef = useRef<Record<string, number>>({});

  const startFetch = useCallback((key: string) => {
    fetchAbortRef.current[key]?.abort(new Error("Superseded"));
    const controller = new AbortController();
    fetchAbortRef.current[key] = controller;
    const seq = (fetchSeqRef.current[key] || 0) + 1;
    fetchSeqRef.current[key] = seq;
    return { controller, current: () => fetchSeqRef.current[key] === seq };
  }, []);

  // Abort everything still in flight when the page unmounts.
  useEffect(() => {
    return () => {
      Object.values(fetchAbortRef.current).forEach((controller) =>
        controller.abort(new Error("Component unmounted"))
      );
      Object.keys(fetchSeqRef.current).forEach((key) => {
        fetchSeqRef.current[key] += 1;
      });
    };
  }, []);

  // 1. Check Admin Auth
  const checkAuth = useCallback(() => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      setLoadingUser(false);
      return;
    }

    setLoadingUser(true);
    let active = true;
    const controller = new AbortController();
    // 3 second failsafe timeout so it never hangs indefinitely
    const timer = setTimeout(() => {
      if (active) {
        controller.abort(new Error("Auth verification timeout"));
        setLoadingUser(false);
      }
    }, 3000);

    apiRequest<any>("/me", { signal: controller.signal })
      .then((res) => {
        if (!active) return;
        clearTimeout(timer);
        setUser(res);
        setLoadingUser(false);
      })
      .catch((err: any) => {
        if (!active) return;
        clearTimeout(timer);
        if (!controller.signal.aborted && err?.code !== "ABORTED") {
          setUser(null);
          setLoadingUser(false);
        }
      });

    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort(new Error("Component unmounted"));
    };
  }, []);

  useEffect(() => {
    // Return the cleanup so unmount aborts the in-flight /me request and clears
    // the 3s failsafe timer.
    return checkAuth();
  }, [checkAuth]);

  // Fetch ETL status
  const fetchEtlData = useCallback(async () => {
    const { controller, current } = startFetch("etl");
    setLoadingLeagues(true);
    try {
      const [lRes, tRes] = await Promise.all([
        apiRequest<any>("/admin/etl/leagues", { signal: controller.signal }),
        apiRequest<any>("/admin/etl/teams", { signal: controller.signal }),
      ]);
      if (!current()) return;
      setLeagues(lRes.leagues || []);
      setTeams(tRes || []);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "Failed to load ETL data.");
    } finally {
      if (current()) setLoadingLeagues(false);
    }
  }, [startFetch]);

  // Fetch Model status
  const fetchModelData = useCallback(async () => {
    const { controller, current } = startFetch("model");
    setLoadingModel(true);
    try {
      const res = await apiRequest<any>("/admin/model/overview", { signal: controller.signal });
      if (!current()) return;
      setModelOverview(res.leagues || []);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "Failed to load model parameters.");
    } finally {
      if (current()) setLoadingModel(false);
    }
  }, [startFetch]);

  // Fetch Billing status
  const fetchBillingData = useCallback(async () => {
    const { controller, current } = startFetch("billing");
    setLoadingBilling(true);
    try {
      const [invRes, uRes] = await Promise.all([
        apiRequest<any>("/admin/billing/invoices", { signal: controller.signal }),
        apiRequest<any>("/admin/billing/users", { signal: controller.signal }),
      ]);
      if (!current()) return;
      setInvoices(invRes || []);
      setUsersList(uRes || []);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "Failed to load invoices.");
    } finally {
      if (current()) setLoadingBilling(false);
    }
  }, [startFetch]);

  // Fetch Settings status
  const fetchSettingsData = useCallback(async () => {
    const { controller, current } = startFetch("settings");
    setLoadingSettings(true);
    try {
      const [lRes, sRes] = await Promise.all([
        apiRequest<any>("/admin/settings/leagues", { signal: controller.signal }),
        apiRequest<any>("/admin/settings/system-info", { signal: controller.signal }),
      ]);
      if (!current()) return;
      setSettingsLeagues(lRes.leagues || []);
      setSystemInfo(sRes || null);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "Failed to load settings data.");
    } finally {
      if (current()) setLoadingSettings(false);
    }
  }, [startFetch]);

  // Fetch Aliases
  const fetchAliasesData = useCallback(async (q?: string) => {
    const { controller, current } = startFetch("aliases");
    setLoadingAliases(true);
    try {
      const url = q ? `/admin/settings/aliases?search=${encodeURIComponent(q)}` : "/admin/settings/aliases";
      const res = await apiRequest<any>(url, { signal: controller.signal });
      if (!current()) return;
      setAliasesList(res.aliases || []);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载别名映射失败。");
    } finally {
      if (current()) setLoadingAliases(false);
    }
  }, [startFetch]);

  // Fetch Quant Config
  const fetchQuantConfig = useCallback(async () => {
    const { controller, current } = startFetch("quant");
    try {
      const res = await apiRequest<any>("/admin/settings/config/quant-risk", { signal: controller.signal });
      if (!current()) return;
      setQuantConfig(res);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载量化参数失败。");
    }
  }, [startFetch]);

  // Fetch Provider Config & Live Quota
  const fetchProviderConfig = useCallback(async () => {
    const { controller, current } = startFetch("provider");
    try {
      const [cfgRes, quotaRes] = await Promise.allSettled([
        apiRequest<any>("/admin/settings/config/data-provider", { signal: controller.signal }),
        apiRequest<any>("/admin/settings/provider/quota", { signal: controller.signal }),
      ]);
      if (!current() || controller.signal.aborted) return;
      if (cfgRes.status === "fulfilled") {
        setProviderConfig(cfgRes.value);
      } else {
        showToast("error", cfgRes.reason?.message || "加载行情源配置失败。");
      }
      if (quotaRes.status === "fulfilled") {
        setQuotaStatus(quotaRes.value);
      }
    } catch (err: any) {
      if (!current() || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载行情源配置失败。");
    }
  }, [startFetch]);

  // Fetch Monetization Config
  const fetchMonetizationConfig = useCallback(async () => {
    const { controller, current } = startFetch("monetization");
    try {
      const res = await apiRequest<any>("/admin/settings/config/monetization", { signal: controller.signal });
      if (!current()) return;
      setMonetizationConfig(res);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载商业化配置失败。");
    }
  }, [startFetch]);

  // Fetch Notifications Config
  const fetchNotifConfig = useCallback(async () => {
    const { controller, current } = startFetch("notif");
    try {
      const res = await apiRequest<any>("/admin/settings/config/notifications", { signal: controller.signal });
      if (!current()) return;
      setNotifConfig(res);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载通知配置失败。");
    }
  }, [startFetch]);

  // Fetch Audit Logs
  const fetchAuditLogs = useCallback(async () => {
    const { controller, current } = startFetch("audit");
    setLoadingAudit(true);
    try {
      const res = await apiRequest<any>("/admin/settings/audit-logs", { signal: controller.signal });
      if (!current()) return;
      setAuditLogs(res.logs || []);
    } catch (err: any) {
      if (!current() || controller.signal.aborted || err?.code === "ABORTED") return;
      showToast("error", err?.message || "加载审计日志失败。");
    } finally {
      if (current()) setLoadingAudit(false);
    }
  }, [startFetch]);

  // Fetch live quota status for top banner & header
  const fetchQuotaStatus = useCallback(async () => {
    const { controller, current } = startFetch("quota");
    try {
      const res = await apiRequest<any>("/admin/settings/provider/quota", { signal: controller.signal });
      if (!current()) return;
      setQuotaStatus(res);
    } catch {
      // silent background refresh
    }
  }, [startFetch]);

  const isAdmin = Boolean(user?.is_admin);

  // Header summary metrics + live quota load once admin auth resolves. These
  // feed the cross-tab stat cards, so they are fetched regardless of the active
  // tab; the per-tab effect below owns the tab's own data and never re-fetches
  // ETL/model/billing for the same screen a second time.
  useEffect(() => {
    if (!isAdmin) return;
    fetchQuotaStatus();
    fetchModelData();
    fetchBillingData();
  }, [isAdmin, fetchQuotaStatus, fetchModelData, fetchBillingData]);

  // Active-tab data: exactly one fetch per (tab, sub-tab/search) change.
  useEffect(() => {
    if (!isAdmin) return;
    if (activeTab === "data_etl") fetchEtlData();
    if (activeTab === "model_ops") fetchModelData();
    if (activeTab === "billing_users") fetchBillingData();
    if (activeTab === "settings") {
      fetchSettingsData();
      if (settingsSubTab === "aliases") fetchAliasesData(debouncedAliasSearch);
      if (settingsSubTab === "quant_risk") fetchQuantConfig();
      if (settingsSubTab === "provider") fetchProviderConfig();
      if (settingsSubTab === "monetization") fetchMonetizationConfig();
      if (settingsSubTab === "notifications") fetchNotifConfig();
      if (settingsSubTab === "audit_cache") fetchAuditLogs();
    }
  }, [
    isAdmin,
    activeTab,
    settingsSubTab,
    debouncedAliasSearch,
    fetchEtlData,
    fetchModelData,
    fetchBillingData,
    fetchSettingsData,
    fetchAliasesData,
    fetchQuantConfig,
    fetchProviderConfig,
    fetchMonetizationConfig,
    fetchNotifConfig,
    fetchAuditLogs,
  ]);

  // Handle Online Remote Sync
  const handleRemoteSync = async () => {
    setSyncingRemote(true);
    setSyncResult(null);
    try {
      const res = await apiRequest<any>("/admin/etl/sync-remote", {
        method: "POST",
        timeoutMs: 180_000,
        body: JSON.stringify({
          league_code: remoteLeagueCode,
          season: remoteSeason,
          auto_train: remoteAutoTrain,
        }),
      });
      setSyncResult(res);
      showToast("success", `同步成功！入库 ${res.matches_inserted} 场，更新 ${res.matches_updated} 场。`);
      fetchEtlData();
    } catch (err: any) {
      if (err?.code === "ABORTED") return;
      showToast("error", err?.message || "在线同步失败，请检查网络或联赛代码。");
    } finally {
      setSyncingRemote(false);
    }
  };

  // Handle CSV Preview
  const handleCsvPreview = async () => {
    if (!csvFile) {
      showToast("error", "请先选择需要上传的 CSV 文件");
      return;
    }
    setPreviewLoading(true);
    setPreviewData(null);
    setCommitResult(null);
    try {
      const formData = new FormData();
      formData.append("file", csvFile);
      formData.append("league_id", previewLeagueId);

      const res = await apiRequest<any>("/admin/etl/upload-csv/preview", {
        method: "POST",
        timeoutMs: 60_000,
        body: formData,
      });
      setPreviewData(res);
      setAliasMappings({});
      showToast("info", `预检完成！识别到 ${res.total_rows} 场比赛，其中 ${res.unknown_teams.length} 个未匹配球队。`);
    } catch (err: any) {
      if (err?.code === "ABORTED") return;
      showToast("error", err?.message || "CSV 解析预检失败。");
    } finally {
      setPreviewLoading(false);
    }
  };

  // Handle CSV Commit
  const handleCsvCommit = async () => {
    if (!previewData || !previewData.csv_content) return;
    setCommittingCsv(true);
    try {
      const res = await apiRequest<any>("/admin/etl/upload-csv/commit", {
        method: "POST",
        timeoutMs: 180_000,
        body: JSON.stringify({
          csv_content: previewData.csv_content,
          league_id: previewLeagueId,
          alias_mappings: Object.fromEntries(
            Object.entries(aliasMappings).filter(([, teamId]) => typeof teamId === "string" && teamId.trim() !== "")
          ),
          auto_train: true,
        }),
      });
      setCommitResult(res);
      showToast("success", `入库完成！新增 ${res.matches_inserted} 场，更新 ${res.matches_updated} 场。`);
      fetchEtlData();
    } catch (err: any) {
      if (err?.code === "ABORTED") return;
      showToast("error", err?.message || "入库提交失败。");
    } finally {
      setCommittingCsv(false);
    }
  };

  // Handle Model Retrain
  const handleModelRetrain = async (leagueId: string) => {
    setRetrainingModel(true);
    try {
      const res = await apiRequest<any>("/admin/model/retrain", {
        method: "POST",
        timeoutMs: 180_000,
        body: JSON.stringify({ league_id: leagueId, refresh_predictions: true }),
      });
      showToast("success", `模型重训完成！主场优势 γ=${res.home_advantage}，低分修正 ρ=${res.rho}`);
      fetchModelData();
    } catch (err: any) {
      if (err?.code === "ABORTED") return;
      showToast("error", err?.message || "模型训练失败。");
    } finally {
      setRetrainingModel(false);
    }
  };

  // Handle Manual Invoice Grant
  const handleManualGrant = async (orderId: string) => {
    if (!confirm(`确定为订单 ${orderId} 手动补单并立即激活该用户的 Analyst 会员权益？`)) return;
    setGrantingOrderId(orderId);
    try {
      const res = await apiRequest<any>(`/admin/billing/invoices/${orderId}/grant`, {
        method: "POST",
      });
      showToast("success", `补单成功！用户 ${res.user_email} 已升级为 ${res.plan_tier}`);
      fetchBillingData();
    } catch (err: any) {
      showToast("error", err?.message || "补单失败。");
    } finally {
      setGrantingOrderId(null);
    }
  };

  // Quick grant 30 days
  const handleGrantUserDays = async (userId: string) => {
    try {
      await apiRequest<any>(`/admin/billing/users/${userId}/grant`, {
        method: "POST",
        body: JSON.stringify({ plan_tier: "ANALYST", add_days: 30 }),
      });
      showToast("success", "已成功为该用户延长 30 天 Analyst 专家权益。");
      fetchBillingData();
    } catch (err: any) {
      showToast("error", err?.message || "赠送权益失败。");
    }
  };

  // Handle Create League
  const handleCreateLeague = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newLeagueId.trim() || !newLeagueName.trim()) {
      showToast("error", "联赛代码与联赛名称不能为空。");
      return;
    }
    setCreatingLeague(true);
    try {
      const res = await apiRequest<any>("/admin/settings/leagues", {
        method: "POST",
        body: JSON.stringify({
          id: newLeagueId.trim(),
          name: newLeagueName.trim(),
          country: newLeagueCountry.trim() || undefined,
          active: newLeagueActive,
        }),
      });
      showToast("success", res.message || `联赛 ${newLeagueName} 创建成功！`);
      setNewLeagueId("");
      setNewLeagueName("");
      setNewLeagueCountry("");
      setShowAddLeague(false);
      fetchSettingsData();
      fetchEtlData();
    } catch (err: any) {
      showToast("error", err?.message || "创建联赛失败。");
    } finally {
      setCreatingLeague(false);
    }
  };

  // Handle Toggle League Active
  const handleToggleLeagueActive = async (leagueId: string, currentActive: boolean) => {
    try {
      const res = await apiRequest<any>(`/admin/settings/leagues/${leagueId}`, {
        method: "PATCH",
        body: JSON.stringify({ active: !currentActive }),
      });
      showToast("success", res.message || `已成功${!currentActive ? "启用" : "停用"}联赛`);
      fetchSettingsData();
      fetchEtlData();
    } catch (err: any) {
      showToast("error", err?.message || "更新联赛状态失败。");
    }
  };

  // Handle Delete League
  const handleDeleteLeague = async (leagueId: string, leagueName: string, matchesCount: number) => {
    if (matchesCount > 0) {
      showToast("error", `该联赛已有 ${matchesCount} 场历史比赛数据，禁止硬删除！如需暂停请点击“停用”操作。`);
      return;
    }
    if (!confirm(`确定要彻底删除联赛 "${leagueName}" (${leagueId}) 吗？此操作无法撤销。`)) {
      return;
    }
    try {
      const res = await apiRequest<any>(`/admin/settings/leagues/${leagueId}`, {
        method: "DELETE",
      });
      showToast("success", res.message || `联赛 ${leagueId} 已删除。`);
      fetchSettingsData();
      fetchEtlData();
    } catch (err: any) {
      showToast("error", err?.message || "删除联赛失败。");
    }
  };

  // Handle Create Team
  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTeamId.trim() || !newTeamName.trim()) {
      showToast("error", "球队代码与官方名称不能为空。");
      return;
    }
    setCreatingTeam(true);
    try {
      const res = await apiRequest<any>("/admin/settings/teams", {
        method: "POST",
        body: JSON.stringify({
          id: newTeamId.trim(),
          canonical_name: newTeamName.trim(),
          country: newTeamCountry.trim() || undefined,
        }),
      });
      showToast("success", res.message || `球队 ${newTeamName} 录入成功！`);
      setNewTeamId("");
      setNewTeamName("");
      setNewTeamCountry("");
      setShowAddTeam(false);
      fetchEtlData();
    } catch (err: any) {
      showToast("error", err?.message || "录入球队失败。");
    } finally {
      setCreatingTeam(false);
    }
  };

  // Handle Create Alias
  const handleCreateAlias = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAliasTeamId.trim() || !newAliasName.trim()) {
      showToast("error", "请选择目标球队并输入别名文本。");
      return;
    }
    setCreatingAlias(true);
    try {
      const res = await apiRequest<any>("/admin/settings/aliases", {
        method: "POST",
        body: JSON.stringify({
          team_id: newAliasTeamId.trim(),
          external_name: newAliasName.trim(),
          source_name: "MANUAL_ADMIN",
        }),
      });
      showToast("success", res.message || "别名绑定成功！");
      setNewAliasName("");
      setShowAddAlias(false);
      fetchAliasesData(aliasSearch);
    } catch (err: any) {
      showToast("error", err?.message || "绑定别名失败。");
    } finally {
      setCreatingAlias(false);
    }
  };

  // Handle Delete Alias
  const handleDeleteAlias = async (aliasId: string, aliasName: string) => {
    if (!confirm(`确定解绑别名 "${aliasName}" 吗？`)) return;
    try {
      const res = await apiRequest<any>(`/admin/settings/aliases/${aliasId}`, {
        method: "DELETE",
      });
      showToast("success", res.message || "别名已成功解绑。");
      fetchAliasesData(aliasSearch);
    } catch (err: any) {
      showToast("error", err?.message || "解绑别名失败。");
    }
  };

  // Handle Save Quant Config
  const handleSaveQuantConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingQuant(true);
    try {
      const res = await apiRequest<any>("/admin/settings/config/quant-risk", {
        method: "PUT",
        body: JSON.stringify(quantConfig),
      });
      showToast("success", res.message || "量化风控参数已保存！");
      fetchSettingsData();
    } catch (err: any) {
      showToast("error", err?.message || "保存量化风控参数失败。");
    } finally {
      setSavingQuant(false);
    }
  };

  // Handle Save Provider Config
  const handleSaveProviderConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProvider(true);
    try {
      const res = await apiRequest<any>("/admin/settings/config/data-provider", {
        method: "PUT",
        body: JSON.stringify(providerConfig),
      });
      showToast("success", res.message || "行情源配置已更新。");
      fetchProviderConfig();
    } catch (err: any) {
      showToast("error", err?.message || "保存行情配置失败。");
    } finally {
      setSavingProvider(false);
    }
  };

  // Handle Check Quota
  const handleCheckQuota = async () => {
    setCheckingQuota(true);
    try {
      const res = await apiRequest<any>("/admin/settings/provider/quota");
      setQuotaStatus(res);
      if (res.status === "HEALTHY") {
        showToast("success", `行情通信正常！剩余配额: ${res.requests_remaining ?? "充足"}`);
      } else {
        showToast("info", res.message || "配额检测完成");
      }
    } catch (err: any) {
      if (err?.code === "ABORTED") return;
      showToast("error", err?.message || "检测配额失败。");
    } finally {
      setCheckingQuota(false);
    }
  };

  // Handle Save Monetization Config
  const handleSaveMonetizationConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingMonetization(true);
    try {
      const res = await apiRequest<any>("/admin/settings/config/monetization", {
        method: "PUT",
        body: JSON.stringify(monetizationConfig),
      });
      showToast("success", res.message || "商业化定价策略已更新！");
    } catch (err: any) {
      showToast("error", err?.message || "保存商业化策略失败。");
    } finally {
      setSavingMonetization(false);
    }
  };

  // Handle Save Notifications Config
  const handleSaveNotifConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingNotif(true);
    try {
      const res = await apiRequest<any>("/admin/settings/config/notifications", {
        method: "PUT",
        body: JSON.stringify(notifConfig),
      });
      showToast("success", res.message || "通知配置已保存！");
      fetchNotifConfig();
    } catch (err: any) {
      showToast("error", err?.message || "保存通知配置失败。");
    } finally {
      setSavingNotif(false);
    }
  };

  // Handle Test Notification
  const handleTestNotif = async (channel: string) => {
    setTestingNotif(true);
    setTestNotifResult(null);
    try {
      const res = await apiRequest<any>("/admin/settings/notifications/test", {
        method: "POST",
        body: JSON.stringify({ channel }),
      });
      setTestNotifResult(res.results);
      showToast("info", "测试广播请求已执行，请查看下方通道响应结果。");
    } catch (err: any) {
      showToast("error", err?.message || "测试通知发送失败。");
    } finally {
      setTestingNotif(false);
    }
  };

  // Handle Purge Cache
  const handlePurgeCache = async () => {
    if (!confirm("确定清空系统中的所有比赛预测和行情热点缓存吗？")) return;
    setPurgingCache(true);
    try {
      const res = await apiRequest<any>("/admin/settings/cache/purge", {
        method: "POST",
      });
      showToast("success", res.message || "缓存清理完成！");
      fetchAuditLogs();
    } catch (err: any) {
      showToast("error", err?.message || "清理缓存失败。");
    } finally {
      setPurgingCache(false);
    }
  };

  if (loadingUser) {
    return (
      <div className="min-h-screen bg-[#080c14] flex items-center justify-center text-slate-400">
        <RefreshCw className="w-6 h-6 animate-spin mr-2 text-blue-500" />
        <span>正在验证管理员身份...</span>
      </div>
    );
  }

  if (!user || !user.is_admin) {
    return (
      <div className="min-h-screen bg-[#080c14] flex flex-col items-center justify-center p-6 text-center">
        <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 flex items-center justify-center mb-4 text-rose-400">
          <Lock className="w-8 h-8" />
        </div>
        <h1 className="text-2xl font-bold text-white mb-2">需要管理员权限 (Access Denied)</h1>
        <p className="text-slate-400 text-sm max-w-md mb-6">
          当前登录状态: <code className="text-amber-400 font-mono">{user?.email || "未登录"}</code>。进入系统运维管理后台需要具备 Administrator 特权。
        </p>
        
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <button
            onClick={() => setIsAuthOpen(true)}
            className="inline-flex items-center px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-sm font-bold transition shadow-lg shadow-amber-500/20"
          >
            <KeyRound className="w-4 h-4 mr-2" />
            登录管理员账号
          </button>

          <Link
            href="/"
            className="inline-flex items-center px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition"
          >
            <ArrowLeft className="w-4 h-4 mr-1.5" />
            返回主终端
          </Link>
        </div>

        <AuthModal
          isOpen={isAuthOpen}
          onClose={() => setIsAuthOpen(false)}
          onSuccess={() => checkAuth()}
        />
      </div>
    );
  }

  const selectedModel = modelOverview.find((m) => m.league_id === selectedModelLeague) || modelOverview[0];

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-100">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl border shadow-xl flex items-center space-x-2 text-sm backdrop-blur-md transition-all ${
            toast.type === "success"
              ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-200"
              : toast.type === "error"
              ? "bg-rose-950/80 border-rose-500/40 text-rose-200"
              : "bg-blue-950/80 border-blue-500/40 text-blue-200"
          }`}
        >
          {toast.type === "success" && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
          {toast.type === "error" && <AlertTriangle className="w-4 h-4 text-rose-400" />}
          {toast.type === "info" && <RefreshCw className="w-4 h-4 text-blue-400" />}
          <span>{toast.message}</span>
        </div>
      )}

      {/* Header */}
      <header className="border-b border-slate-800 bg-[#0c121f]/90 sticky top-0 z-30 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <Link
              href="/"
              className="flex items-center space-x-2.5 group cursor-pointer hover:opacity-95 transition"
              title="返回首页"
            >
              <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-base text-white shadow-lg shadow-blue-500/20 group-hover:bg-blue-500 transition">
                λ
              </div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg text-white tracking-tight group-hover:text-blue-300 transition">
                  MatchLambda
                </span>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-500/10 text-amber-400 border border-amber-500/30 font-mono">
                  OPS ADMIN
                </span>
              </div>
            </Link>
            <span className="text-slate-700">|</span>
            <Link
              href="/"
              className="flex items-center space-x-1.5 text-slate-400 hover:text-white transition px-2 py-1 rounded bg-slate-900/60 border border-slate-800 text-xs font-mono"
              title="返回主终端 / Terminal"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>终端</span>
            </Link>
          </div>

          <div className="flex items-center space-x-3 text-xs">
            {quotaStatus && (
              <button
                type="button"
                onClick={() => {
                  setActiveTab("settings");
                  setSettingsSubTab("provider");
                }}
                className={`hidden sm:flex items-center space-x-1.5 px-3 py-1 rounded-lg border font-mono transition text-xs ${
                  quotaStatus.status === "HEALTHY"
                    ? quotaStatus.requests_remaining !== null && quotaStatus.requests_remaining < 50
                      ? "bg-amber-500/10 border-amber-500/30 text-amber-300 hover:bg-amber-500/20"
                      : "bg-blue-500/10 border-blue-500/30 text-blue-300 hover:bg-blue-500/20"
                    : "bg-rose-500/10 border-rose-500/30 text-rose-300 hover:bg-rose-500/20"
                }`}
                title="点击跳转至行情源与配额详情设置"
              >
                <Radio className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
                <span className="text-slate-400">行情API配额:</span>
                <span className="font-bold text-white">
                  {quotaStatus.requests_remaining !== null ? `${quotaStatus.requests_remaining} 次` : quotaStatus.status}
                </span>
                {quotaStatus.requests_used !== null && (
                  <span className="text-[10px] text-slate-400 font-sans">
                    (已用 {quotaStatus.requests_used})
                  </span>
                )}
              </button>
            )}

            <span className="text-slate-400 font-mono hidden md:inline">Admin: {user.email}</span>
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse"></span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Global Live Ops Bar */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {/* 1. Odds API Quota Card */}
          <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-4 backdrop-blur shadow-lg flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                <Radio className="w-3.5 h-3.5 text-blue-400" />
                <span>行情源 API 配额</span>
              </span>
              <button
                type="button"
                onClick={handleCheckQuota}
                disabled={checkingQuota}
                className="p-1 hover:bg-slate-800 rounded-md text-slate-400 hover:text-white transition"
                title="立即刷新检测配额"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${checkingQuota ? "animate-spin text-blue-400" : ""}`} />
              </button>
            </div>
            <div className="flex items-baseline justify-between">
              <div className="flex items-baseline space-x-1.5">
                <span className="text-2xl font-black text-white font-mono">
                  {quotaStatus?.requests_remaining !== null && quotaStatus?.requests_remaining !== undefined
                    ? quotaStatus.requests_remaining
                    : "—"}
                </span>
                <span className="text-xs text-slate-400">次可用</span>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold font-mono ${
                  quotaStatus?.status === "HEALTHY"
                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "bg-slate-800 text-slate-400"
                }`}
              >
                {quotaStatus?.status || "CHECKING"}
              </span>
            </div>
            <div className="text-[11px] text-slate-400 mt-2 flex items-center justify-between border-t border-slate-800/80 pt-2 font-mono">
              <span>已消耗: {quotaStatus?.requests_used ?? 0} 次</span>
              <button
                type="button"
                onClick={() => {
                  setActiveTab("settings");
                  setSettingsSubTab("provider");
                }}
                className="text-blue-400 hover:underline font-sans"
              >
                源配置 →
              </button>
            </div>
          </div>

          {/* 2. Database Entities Card */}
          <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-4 backdrop-blur shadow-lg flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                <Database className="w-3.5 h-3.5 text-emerald-400" />
                <span>已录入赛事实体</span>
              </span>
              <span className="text-[10px] text-emerald-400 font-mono bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20 font-bold">
                POSTGRES
              </span>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-white font-mono">{leagues.length}</span>
              <span className="text-xs text-slate-400">联赛</span>
              <span className="text-slate-600 font-mono">/</span>
              <span className="text-2xl font-black text-white font-mono">{teams.length}</span>
              <span className="text-xs text-slate-400">球队</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-2 border-t border-slate-800/80 pt-2 flex items-center justify-between font-mono">
              <span>全量历史赛果库</span>
              <button
                type="button"
                onClick={() => setActiveTab("data_etl")}
                className="text-emerald-400 hover:underline font-sans"
              >
                ETL 管理 →
              </button>
            </div>
          </div>

          {/* 3. Model Engine Card */}
          <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-4 backdrop-blur shadow-lg flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                <Brain className="w-3.5 h-3.5 text-indigo-400" />
                <span>量化二元分布拟合</span>
              </span>
              <span className="text-[10px] text-indigo-400 font-mono bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20 font-bold">
                DIXON-COLES
              </span>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-white font-mono">{modelOverview.length || leagues.length}</span>
              <span className="text-xs text-slate-400">参数集已就绪</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-2 border-t border-slate-800/80 pt-2 flex items-center justify-between font-mono">
              <span>Shin 去抽水 + 凯利风控</span>
              <button
                type="button"
                onClick={() => setActiveTab("model_ops")}
                className="text-indigo-400 hover:underline font-sans"
              >
                参数中心 →
              </button>
            </div>
          </div>

          {/* 4. Billing & Monetization Card */}
          <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-4 backdrop-blur shadow-lg flex flex-col justify-between">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-400 flex items-center space-x-1.5">
                <CreditCard className="w-3.5 h-3.5 text-amber-400" />
                <span>商业化与会员</span>
              </span>
              <span className="text-[10px] text-amber-400 font-mono bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20 font-bold">
                NOWPAYMENTS
              </span>
            </div>
            <div className="flex items-baseline space-x-2">
              <span className="text-2xl font-black text-white font-mono">{usersList.length || "—"}</span>
              <span className="text-xs text-slate-400">注册用户</span>
            </div>
            <div className="text-[11px] text-slate-400 mt-2 border-t border-slate-800/80 pt-2 flex items-center justify-between font-mono">
              <span>已记录订单: {invoices.length} 笔</span>
              <button
                type="button"
                onClick={() => setActiveTab("billing_users")}
                className="text-amber-400 hover:underline font-sans"
              >
                查看流水 →
              </button>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 mb-8 space-x-2">
          <button
            onClick={() => setActiveTab("data_etl")}
            className={`flex items-center space-x-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
              activeTab === "data_etl"
                ? "border-blue-500 text-blue-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Database className="w-4 h-4" />
            <span>历史数据导入与 ETL</span>
          </button>

          <button
            onClick={() => setActiveTab("model_ops")}
            className={`flex items-center space-x-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
              activeTab === "model_ops"
                ? "border-indigo-500 text-indigo-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Brain className="w-4 h-4" />
            <span>量化模型与参数中心</span>
          </button>

          <button
            onClick={() => setActiveTab("billing_users")}
            className={`flex items-center space-x-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
              activeTab === "billing_users"
                ? "border-amber-500 text-amber-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <CreditCard className="w-4 h-4" />
            <span>订单流水与用户运维</span>
          </button>

          <button
            onClick={() => setActiveTab("settings")}
            className={`flex items-center space-x-2 py-3 px-4 text-sm font-semibold border-b-2 transition ${
              activeTab === "settings"
                ? "border-emerald-500 text-emerald-400"
                : "border-transparent text-slate-400 hover:text-slate-200"
            }`}
          >
            <Settings className="w-4 h-4" />
            <span>联赛与系统配置</span>
          </button>
        </div>

        {/* TAB 1: DATA & ETL */}
        {activeTab === "data_etl" && (
          <div className="space-y-8">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
              {/* Online Sync Card */}
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
                <div className="flex items-center space-x-2.5 mb-4">
                  <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
                    <RefreshCw className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white">在线一键同步 (football-data.co.uk)</h2>
                    <p className="text-xs text-slate-400">官方标准赛果与机构终赔，支持断点补录与自动更新</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1.5">目标联赛</label>
                      <CustomSelect
                        value={remoteLeagueCode}
                        onChange={setRemoteLeagueCode}
                        options={REMOTE_LEAGUE_OPTIONS}
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1.5">赛季 (Season)</label>
                      <CustomSelect
                        value={remoteSeason}
                        onChange={setRemoteSeason}
                        options={AVAILABLE_SEASONS.map((s) => ({
                          value: s.code,
                          label: s.label,
                        }))}
                      />
                    </div>
                  </div>

                  <div className="flex items-center space-x-2 pt-1">
                    <input
                      type="checkbox"
                      id="remoteAutoTrain"
                      checked={remoteAutoTrain}
                      onChange={(e) => setRemoteAutoTrain(e.target.checked)}
                      className="rounded bg-slate-900 border-slate-700 text-blue-600 focus:ring-blue-500 h-4 w-4"
                    />
                    <label htmlFor="remoteAutoTrain" className="text-xs text-slate-300 cursor-pointer">
                      入库完成后自动重新拟合 Dixon-Coles 参数 (推荐)
                    </label>
                  </div>

                  <button
                    onClick={handleRemoteSync}
                    disabled={syncingRemote}
                    className="w-full py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold text-sm transition flex items-center justify-center space-x-2 shadow-lg shadow-blue-500/20"
                  >
                    {syncingRemote ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>正在拉取外部数据并解析入库...</span>
                      </>
                    ) : (
                      <>
                        <Zap className="w-4 h-4" />
                        <span>开始在线抓取并入库</span>
                      </>
                    )}
                  </button>

                  {syncResult && (
                    <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-xs text-emerald-300 space-y-1">
                      <div className="font-bold flex items-center">
                        <CheckCircle2 className="w-4 h-4 mr-1.5 text-emerald-400" />
                        拉取成功：{syncResult.league_id}
                      </div>
                      <div className="text-slate-400 font-mono">
                        新增比赛: {syncResult.matches_inserted} 场 | 更新比分: {syncResult.matches_updated} 场
                        {syncResult.model_trained && " | 模型已完成自动重训"}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* CSV Upload & Preview Card */}
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
                <div className="flex items-center space-x-2.5 mb-4">
                  <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                    <Upload className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-base font-bold text-white">本地 CSV 预检与智能导入 (Dry-Run)</h2>
                    <p className="text-xs text-slate-400">导入前自动拦截未知球队别名，杜绝脏数据导致预测失效</p>
                  </div>
                </div>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1.5">归属联赛</label>
                      <CustomSelect
                        value={previewLeagueId}
                        onChange={setPreviewLeagueId}
                        buttonClassName="focus:border-indigo-500"
                        options={leagues.map((l) => ({
                          value: l.id,
                          label: formatLeagueLabel(l.id, l.name),
                        }))}
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-400 mb-1.5">选择 CSV 文件</label>
                      <input
                        type="file"
                        accept=".csv"
                        onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
                        className="w-full text-xs text-slate-400 file:mr-2 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-slate-800 file:text-slate-200 hover:file:bg-slate-700 cursor-pointer"
                      />
                    </div>
                  </div>

                  <button
                    onClick={handleCsvPreview}
                    disabled={previewLoading || !csvFile}
                    className="w-full py-2.5 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-sm transition flex items-center justify-center space-x-2 shadow-lg shadow-indigo-500/20"
                  >
                    {previewLoading ? (
                      <>
                        <RefreshCw className="w-4 h-4 animate-spin" />
                        <span>正在预检解析 CSV 文件...</span>
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4" />
                        <span>执行预检解析 (Dry-Run Preview)</span>
                      </>
                    )}
                  </button>

                  {commitResult && (
                    <div className="p-3.5 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-xs text-emerald-300 space-y-1">
                      <div className="font-bold flex items-center">
                        <CheckCircle2 className="w-4 h-4 mr-1.5 text-emerald-400" />
                        入库成功：新增 {commitResult.matches_inserted} 场，更新 {commitResult.matches_updated} 场
                      </div>
                      {commitResult.model_trained && (
                        <div className="text-slate-400 font-mono">
                          Dixon-Coles 模型已更新：γ={commitResult.model_param?.home_advantage}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* CSV Preview Inspection Modal/Card */}
            {previewData && (
              <div className="bg-[#0f172a] border border-indigo-500/40 rounded-2xl p-6 shadow-2xl space-y-6">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                  <div>
                    <h3 className="text-base font-bold text-white flex items-center">
                      <FileText className="w-5 h-5 mr-2 text-indigo-400" />
                      预检报告 (Dry-Run Preview Report)
                    </h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      识别到总计 {previewData.total_rows} 行数据，完赛场次 {previewData.finished_matches} 场，待赛场次 {previewData.scheduled_matches} 场
                    </p>
                  </div>
                  <button
                    onClick={handleCsvCommit}
                    disabled={committingCsv}
                    className="py-2.5 px-5 rounded-xl bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white font-bold text-sm transition flex items-center space-x-2 shadow-lg shadow-emerald-500/20"
                  >
                    {committingCsv ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <CheckCircle2 className="w-4 h-4" />
                    )}
                    <span>确认写入数据库并重训模型</span>
                  </button>
                </div>

                {/* Unknown Team Alias Resolution */}
                {previewData.unknown_teams && previewData.unknown_teams.length > 0 ? (
                  <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/40 text-amber-200">
                    <div className="flex items-center space-x-2 font-bold text-sm mb-2 text-amber-400">
                      <AlertTriangle className="w-4 h-4" />
                      <span>发现 {previewData.unknown_teams.length} 个未匹配的球队别名（必须确认绑定后导入）:</span>
                    </div>
                    <p className="text-xs text-slate-400 mb-3">
                      相近名称只作为候选列出，不会自动选中。请手动指定标准球队后，系统才会记录别名。
                    </p>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      {previewData.unknown_teams.map((rawTeam: string) => {
                        const rawSuggestions = previewData.suggested_mappings?.[rawTeam];
                        const candidates = Array.isArray(rawSuggestions) ? rawSuggestions : [];
                        return (
                        <div key={rawTeam} className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                          <div className="flex items-center justify-between">
                            <span className="font-mono text-xs text-amber-300 font-semibold">{rawTeam}</span>
                            <span className="text-slate-600 mx-2">➔</span>
                            <div className="w-56 shrink-0">
                              <CustomSelect
                                value={aliasMappings[rawTeam] || ""}
                                onChange={(val) =>
                                  setAliasMappings((prev) => ({ ...prev, [rawTeam]: val }))
                                }
                                placeholder="-- 请选择匹配球队 --"
                                buttonClassName="bg-slate-800 border-slate-700 py-1 px-2.5 text-xs focus:border-amber-500"
                                options={[
                                  { value: "", label: "-- 清空/不绑定 --" },
                                  ...teams.map((t) => ({
                                    value: t.id,
                                    label: `${t.canonical_name} (${t.country || t.id})`,
                                  })),
                                ]}
                              />
                            </div>
                          </div>
                          {candidates.length > 0 && (
                            <p className="text-[10px] text-slate-500 mt-1.5 leading-relaxed">
                              候选：{candidates.map((item: { team_name?: string; team_id?: string }) => `${item.team_name || item.team_id}`).join("、")}
                            </p>
                          )}
                        </div>
                        );
                      })}
                    </div>
                  </div>
                ) : (
                  <div className="p-3 rounded-xl bg-emerald-950/30 border border-emerald-500/30 text-emerald-300 text-xs flex items-center">
                    <CheckCircle2 className="w-4 h-4 mr-2 text-emerald-400" />
                    所有主客队名称均已精确匹配系统标准球队，无需额外绑定别名。
                  </div>
                )}

                {/* Sample Matches Table */}
                <div>
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
                    前 5 场比赛采样解析预览
                  </h4>
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-900/80 text-slate-400 font-mono">
                        <tr>
                          <th className="py-2.5 px-3">日期</th>
                          <th className="py-2.5 px-3">主队 (原始 ➔ 解析)</th>
                          <th className="py-2.5 px-3">客队 (原始 ➔ 解析)</th>
                          <th className="py-2.5 px-3">比分</th>
                          <th className="py-2.5 px-3">状态</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono">
                        {previewData.sample_matches?.map((m: any) => (
                          <tr
                            key={`${m.date ?? ""}-${m.home_raw ?? ""}-${m.away_raw ?? ""}`}
                            className="hover:bg-slate-900/40"
                          >
                            <td className="py-2 px-3 text-slate-400">{m.date}</td>
                            <td className="py-2 px-3">
                              <span className="text-slate-300">{m.home_raw}</span>
                              <span className="text-slate-600 mx-1">➔</span>
                              <span className="text-blue-400 font-bold">{m.home_id || aliasMappings[m.home_raw] || "未匹配"}</span>
                            </td>
                            <td className="py-2 px-3">
                              <span className="text-slate-300">{m.away_raw}</span>
                              <span className="text-slate-600 mx-1">➔</span>
                              <span className="text-blue-400 font-bold">{m.away_id || aliasMappings[m.away_raw] || "未匹配"}</span>
                            </td>
                            <td className="py-2 px-3 text-slate-200">
                              {m.fthg !== null && m.ftag !== null ? `${m.fthg} - ${m.ftag}` : "-"}
                            </td>
                            <td className="py-2 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                                  m.status === "FINISHED"
                                    ? "bg-emerald-500/10 text-emerald-400"
                                    : "bg-slate-800 text-slate-400"
                                }`}
                              >
                                {m.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* Current Leagues Ingestion Status Table */}
            <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-white flex items-center">
                  <Database className="w-4 h-4 mr-2 text-blue-400" />
                  当前数据库联赛收录现状
                </h3>
                <button
                  onClick={fetchEtlData}
                  disabled={loadingLeagues}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingLeagues ? "animate-spin" : ""}`} />
                  <span>刷新统计</span>
                </button>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-900/80 text-slate-400 font-mono">
                    <tr>
                      <th className="py-2.5 px-3">联赛 ID</th>
                      <th className="py-2.5 px-3">联赛全称</th>
                      <th className="py-2.5 px-3">国家/地区</th>
                      <th className="py-2.5 px-3">总比赛场次</th>
                      <th className="py-2.5 px-3">完赛场次</th>
                      <th className="py-2.5 px-3">最近比赛时间</th>
                      <th className="py-2.5 px-3">状态</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {leagues.map((l) => (
                      <tr key={l.id} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 font-bold text-white">{l.id}</td>
                        <td className="py-2.5 px-3 text-slate-300">
                          {LEAGUE_ZH_NAMES[l.id] ? (
                            <span>
                              <span className="text-white font-bold mr-1.5">{LEAGUE_ZH_NAMES[l.id]}</span>
                              <span className="text-slate-400 text-[11px]">({l.name})</span>
                            </span>
                          ) : (
                            l.name
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-400">{l.country}</td>
                        <td className="py-2.5 px-3 text-blue-400 font-bold">{l.total_matches}</td>
                        <td className="py-2.5 px-3 text-emerald-400 font-bold">{l.finished_matches}</td>
                        <td className="py-2.5 px-3 text-slate-400">{l.latest_match_date ? l.latest_match_date.slice(0, 10) : "-"}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                              l.active ? "bg-emerald-500/10 text-emerald-400" : "bg-slate-800 text-slate-500"
                            }`}
                          >
                            {l.active ? "ACTIVE" : "INACTIVE"}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: MODEL OPS */}
        {activeTab === "model_ops" && (
          <div className="space-y-8">
            {/* Model Header & Selector */}
            <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-bold text-white flex items-center">
                  <Brain className="w-5 h-5 mr-2 text-indigo-400" />
                  Dixon-Coles 量化参数与球队攻防战力榜
                </h2>
                <p className="text-xs text-slate-400 mt-1">
                  基于时间衰减泊松似然优化，包含主场优势 γ、低分相关系数 ρ 以及各队对数攻防强度
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <div className="w-64">
                  <CustomSelect
                    value={selectedModelLeague}
                    onChange={setSelectedModelLeague}
                    buttonClassName="focus:border-indigo-500"
                    options={modelOverview.map((m) => ({
                      value: m.league_id,
                      label: formatLeagueLabel(m.league_id, m.league_name),
                    }))}
                  />
                </div>

                <button
                  onClick={() => handleModelRetrain(selectedModelLeague)}
                  disabled={retrainingModel}
                  className="py-2 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold text-xs transition flex items-center space-x-1.5 shadow-lg shadow-indigo-500/20"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${retrainingModel ? "animate-spin" : ""}`} />
                  <span>一键重新拟合</span>
                </button>
              </div>
            </div>

            {selectedModel?.latest_parameter ? (
              <div className="space-y-8">
                {/* Parameter Metric Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <span className="text-xs text-slate-400">主场优势 (γ Home Adv)</span>
                    <div className="text-xl font-extrabold text-blue-400 font-mono mt-1">
                      +{selectedModel.latest_parameter.home_advantage_gamma}
                    </div>
                    <span className="text-[10px] text-slate-500">Log-scale 进球期望增益</span>
                  </div>

                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <span className="text-xs text-slate-400">低分修正系数 (ρ Rho)</span>
                    <div className="text-xl font-extrabold text-indigo-400 font-mono mt-1">
                      {selectedModel.latest_parameter.rho}
                    </div>
                    <span className="text-[10px] text-slate-500">0-0/1-1 相关性修正</span>
                  </div>

                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <span className="text-xs text-slate-400">时间衰减率 (ξ Decay)</span>
                    <div className="text-xl font-extrabold text-slate-200 font-mono mt-1">
                      {selectedModel.latest_parameter.xi_decay} /day
                    </div>
                    <span className="text-[10px] text-slate-500">半衰期 ~385 天</span>
                  </div>

                  <div className="bg-slate-900/60 border border-slate-800 p-4 rounded-xl">
                    <span className="text-xs text-slate-400">训练样本截止时间</span>
                    <div className="text-sm font-bold text-emerald-400 font-mono mt-2 truncate">
                      {safeSlice(selectedModel.latest_parameter.training_cutoff, 0, 10)}
                    </div>
                    <span className="text-[10px] text-slate-500">{selectedModel.completed_matches} 场完赛数据</span>
                  </div>
                </div>

                {/* Team Ratings Ranking */}
                <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
                  <h3 className="text-sm font-bold text-white mb-4 flex items-center">
                    <Award className="w-4 h-4 mr-2 text-amber-400" />
                    各队进攻强度 α 与防守抗性 β 战力分布
                  </h3>

                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-900/80 text-slate-400 font-mono">
                        <tr>
                          <th className="py-2.5 px-3">排名</th>
                          <th className="py-2.5 px-3">球队</th>
                          <th className="py-2.5 px-3">进攻强度 (α Attack)</th>
                          <th className="py-2.5 px-3">防守抗性 (β Defense)</th>
                          <th className="py-2.5 px-3">综合净评级 (α + β)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono">
                        {selectedModel.team_ratings?.map((t: any, idx: number) => (
                          <tr key={t.team_id} className="hover:bg-slate-900/40">
                            <td className="py-2.5 px-3 font-bold text-slate-500">#{idx + 1}</td>
                            <td className="py-2.5 px-3 font-bold text-white">{t.team_name}</td>
                            <td className="py-2.5 px-3">
                              <span className={t.attack_alpha >= 0 ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                                {t.attack_alpha >= 0 ? `+${t.attack_alpha}` : t.attack_alpha}
                              </span>
                            </td>
                            <td className="py-2.5 px-3">
                              <span className={t.defense_beta >= 0 ? "text-blue-400 font-bold" : "text-amber-400 font-bold"}>
                                {t.defense_beta >= 0 ? `+${t.defense_beta}` : t.defense_beta}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-slate-200 font-bold">
                              {t.net_rating >= 0 ? `+${t.net_rating}` : t.net_rating}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-slate-400 bg-slate-900/40 rounded-2xl border border-slate-800">
                <Brain className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                <p>该联赛尚未进行初次参数拟合。请先导入历史完赛数据后点击“一键重新拟合”。</p>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: BILLING & USERS */}
        {activeTab === "billing_users" && (
          <div className="space-y-8">
            {/* Invoices List */}
            <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-base font-bold text-white flex items-center">
                  <CreditCard className="w-4 h-4 mr-2 text-amber-400" />
                  NOWPayments 加密货币订单流水 (最近 50 笔)
                </h3>
                <button
                  onClick={fetchBillingData}
                  disabled={loadingBilling}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center space-x-1"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${loadingBilling ? "animate-spin" : ""}`} />
                  <span>刷新订单</span>
                </button>
              </div>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-900/80 text-slate-400 font-mono">
                    <tr>
                      <th className="py-2.5 px-3">订单号 (Order ID)</th>
                      <th className="py-2.5 px-3">用户邮箱</th>
                      <th className="py-2.5 px-3">套餐类型</th>
                      <th className="py-2.5 px-3">金额 (USD)</th>
                      <th className="py-2.5 px-3">支付状态</th>
                      <th className="py-2.5 px-3">创建时间</th>
                      <th className="py-2.5 px-3">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {invoices.map((inv) => (
                      <tr key={inv.id} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 text-slate-300 font-bold">{inv.order_id}</td>
                        <td className="py-2.5 px-3 text-slate-200">{inv.user_email}</td>
                        <td className="py-2.5 px-3 text-slate-400">{inv.plan_type}</td>
                        <td className="py-2.5 px-3 text-emerald-400 font-bold">${inv.amount_usd}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              inv.payment_status === "PAID"
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : inv.payment_status === "PENDING"
                                ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {inv.payment_status}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-500">{safeSlice(inv.created_at, 0, 16).replace("T", " ")}</td>
                        <td className="py-2.5 px-3">
                          {inv.payment_status !== "PAID" && (
                            <button
                              onClick={() => handleManualGrant(inv.order_id)}
                              disabled={grantingOrderId === inv.order_id}
                              className="px-2.5 py-1 rounded bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 text-amber-400 font-bold transition text-[11px]"
                            >
                              {grantingOrderId === inv.order_id ? "处理中..." : "⚡ 手动补单"}
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Users List */}
            <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
              <h3 className="text-base font-bold text-white mb-4 flex items-center">
                <Users className="w-4 h-4 mr-2 text-blue-400" />
                用户列表与权限调整
              </h3>

              <div className="overflow-x-auto rounded-xl border border-slate-800">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-900/80 text-slate-400 font-mono">
                    <tr>
                      <th className="py-2.5 px-3">用户邮箱</th>
                      <th className="py-2.5 px-3">订阅级别</th>
                      <th className="py-2.5 px-3">专家权益到期时间</th>
                      <th className="py-2.5 px-3">管理员</th>
                      <th className="py-2.5 px-3">注册时间</th>
                      <th className="py-2.5 px-3">操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {usersList.map((u) => (
                      <tr key={u.id} className="hover:bg-slate-900/40">
                        <td className="py-2.5 px-3 text-white font-bold">{u.email}</td>
                        <td className="py-2.5 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              u.is_active_analyst
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-slate-800 text-slate-400"
                            }`}
                          >
                            {u.is_active_analyst ? "ANALYST 专家" : "FREE 免费"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-slate-300 font-mono">
                          {u.plan_expires_at ? safeSlice(u.plan_expires_at, 0, 10) : "永久免费"}
                        </td>
                        <td className="py-2.5 px-3">
                          {u.is_admin ? (
                            <span className="text-amber-400 font-bold">ADMIN</span>
                          ) : (
                            <span className="text-slate-500">-</span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 text-slate-500">{safeSlice(u.created_at, 0, 10)}</td>
                        <td className="py-2.5 px-3">
                          <button
                            onClick={() => handleGrantUserDays(u.id)}
                            className="px-2 py-1 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 transition text-[10px] font-bold"
                          >
                            +30天专家
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* TAB 4: SETTINGS & SYSTEM CONFIGURATION */}
        {activeTab === "settings" && (
          <div className="space-y-6">
            {/* Secondary Sub-Tabs Navigation */}
            <div className="flex flex-wrap items-center gap-1.5 p-1.5 bg-[#0f172a]/90 rounded-2xl border border-slate-800">
              <button
                onClick={() => setSettingsSubTab("leagues")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "leagues"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Globe2 className="w-3.5 h-3.5" />
                <span>联赛与球队</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("aliases")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "aliases"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Link2 className="w-3.5 h-3.5" />
                <span>球队别名字典</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("quant_risk")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "quant_risk"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>量化风控调参</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("provider")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "provider"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Activity className="w-3.5 h-3.5" />
                <span>行情源与配额</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("monetization")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "monetization"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Coins className="w-3.5 h-3.5" />
                <span>订阅定价策略</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("notifications")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "notifications"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <Bell className="w-3.5 h-3.5" />
                <span>即时告警推送</span>
              </button>

              <button
                onClick={() => setSettingsSubTab("audit_cache")}
                className={`flex items-center space-x-1.5 px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                  settingsSubTab === "audit_cache"
                    ? "bg-emerald-500 text-slate-950 shadow-lg shadow-emerald-500/20"
                    : "text-slate-400 hover:text-white hover:bg-slate-800/60"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>审计与缓存</span>
              </button>
            </div>

            {/* SUBTAB 1: LEAGUES & TEAMS */}
            {settingsSubTab === "leagues" && (
              <div className="space-y-8">
                {/* Action Bar & Forms */}
                <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                    <div>
                      <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                        <Globe2 className="w-5 h-5 text-emerald-400" />
                        <span>联赛管理与入库配置 (League Management)</span>
                      </h2>
                      <p className="text-xs text-slate-400 mt-1">
                        在此处注册新联赛、管理赛事激活状态或登记官方球队。新加入的联赛将自动挂载至历史数据 ETL、远程同步及量化模型中心。
                      </p>
                    </div>

                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => {
                          setShowAddLeague(!showAddLeague);
                          if (showAddTeam) setShowAddTeam(false);
                        }}
                        className={`inline-flex items-center px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg ${
                          showAddLeague
                            ? "bg-slate-700 text-white"
                            : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20"
                        }`}
                      >
                        <Plus className="w-4 h-4 mr-1.5" />
                        {showAddLeague ? "收起表单" : "新增联赛"}
                      </button>

                      <button
                        onClick={() => {
                          setShowAddTeam(!showAddTeam);
                          if (showAddLeague) setShowAddLeague(false);
                        }}
                        className={`inline-flex items-center px-3.5 py-2 rounded-xl text-xs font-bold transition ${
                          showAddTeam
                            ? "bg-slate-700 text-white"
                            : "bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700"
                        }`}
                      >
                        <Users className="w-4 h-4 mr-1.5 text-blue-400" />
                        {showAddTeam ? "收起表单" : "录入球队"}
                      </button>

                      <button
                        onClick={fetchSettingsData}
                        disabled={loadingSettings}
                        className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                        title="刷新列表"
                      >
                        <RefreshCw className={`w-4 h-4 ${loadingSettings ? "animate-spin text-emerald-400" : ""}`} />
                      </button>
                    </div>
                  </div>

                  {/* Form 1: Add New League */}
                  {showAddLeague && (
                    <div className="mb-6 p-5 rounded-xl bg-slate-900/90 border border-emerald-500/30 shadow-inner">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-bold text-emerald-400 flex items-center">
                          <Plus className="w-4 h-4 mr-1.5" />
                          创建新赛事 / 联赛 (Create New League)
                        </h3>
                        <span className="text-[11px] text-slate-400">所有字段均为必须或标准格式</span>
                      </div>

                      <form onSubmit={handleCreateLeague} className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            联赛唯一标识码 (League ID) <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="如: J_LEAGUE, MLS, SAUDI_PRO"
                            value={newLeagueId}
                            onChange={(e) => setNewLeagueId(e.target.value.toUpperCase())}
                            required
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500 uppercase"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">全局唯一英文大写/下划线代号</span>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            联赛全称 (Official Name) <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="如: J1 League (日职联)"
                            value={newLeagueName}
                            onChange={(e) => setNewLeagueName(e.target.value)}
                            required
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">官方显示全称 (中/英均可)</span>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            所属国家或地区 (Country/Region) <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="如: Japan, Saudi Arabia, USA"
                            value={newLeagueCountry}
                            onChange={(e) => setNewLeagueCountry(e.target.value)}
                            required
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">国家标准英文或中文名称</span>
                        </div>

                        <div className="md:col-span-3 flex items-center justify-between pt-2 border-t border-slate-800">
                          <label className="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={newLeagueActive}
                              onChange={(e) => setNewLeagueActive(e.target.checked)}
                              className="rounded border-slate-700 text-emerald-500 focus:ring-emerald-500 bg-slate-950"
                            />
                            <span>立即激活该联赛（允许实时数据采集与量化分析）</span>
                          </label>

                          <div className="flex items-center space-x-3">
                            <button
                              type="button"
                              onClick={() => setShowAddLeague(false)}
                              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                            >
                              取消
                            </button>
                            <button
                              type="submit"
                              disabled={creatingLeague}
                              className="px-5 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                            >
                              {creatingLeague ? "正在提交..." : "确认创建联赛"}
                            </button>
                          </div>
                        </div>
                      </form>
                    </div>
                  )}

                  {/* Form 2: Add New Team */}
                  {showAddTeam && (
                    <div className="mb-6 p-5 rounded-xl bg-slate-900/90 border border-blue-500/30 shadow-inner">
                      <div className="flex items-center justify-between mb-4">
                        <h3 className="text-sm font-bold text-blue-400 flex items-center">
                          <Users className="w-4 h-4 mr-1.5" />
                          录入官方标准球队 (Register Canonical Team)
                        </h3>
                        <span className="text-[11px] text-slate-400">用于消歧义映射与队伍标准化</span>
                      </div>

                      <form onSubmit={handleCreateTeam} className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            球队标准代号 (Slug ID) <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="如: vissel-kobe, al-hilal"
                            value={newTeamId}
                            onChange={(e) => setNewTeamId(e.target.value.toLowerCase().replace(/\s+/g, "-"))}
                            required
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-blue-500 lowercase"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">全小写字母/短横线 slug</span>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            官方标准名称 (Canonical Name) <span className="text-rose-400">*</span>
                          </label>
                          <input
                            type="text"
                            placeholder="如: Vissel Kobe (神户胜利船)"
                            value={newTeamName}
                            onChange={(e) => setNewTeamName(e.target.value)}
                            required
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">官方标准命名</span>
                        </div>

                        <div>
                          <label className="block text-xs font-semibold text-slate-300 mb-1">
                            所属国家 (Country)
                          </label>
                          <input
                            type="text"
                            placeholder="如: Japan"
                            value={newTeamCountry}
                            onChange={(e) => setNewTeamCountry(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-blue-500"
                          />
                          <span className="text-[10px] text-slate-400 mt-1 block">选填</span>
                        </div>

                        <div className="md:col-span-3 flex justify-end space-x-3 pt-2 border-t border-slate-800">
                          <button
                            type="button"
                            onClick={() => setShowAddTeam(false)}
                            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                          >
                            取消
                          </button>
                          <button
                            type="submit"
                            disabled={creatingTeam}
                            className="px-5 py-2 rounded-lg bg-blue-500 hover:bg-blue-400 text-white text-xs font-bold transition shadow-lg shadow-blue-500/20 disabled:opacity-50"
                          >
                            {creatingTeam ? "正在录入..." : "确认录入球队"}
                          </button>
                        </div>
                      </form>
                    </div>
                  )}

                  {/* Filter / Search Bar */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                    <div className="relative max-w-sm w-full">
                      <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                      <input
                        type="text"
                        placeholder="按联赛代号、名称或国家过滤..."
                        value={leagueSearchQuery}
                        onChange={(e) => setLeagueSearchQuery(e.target.value)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-600"
                      />
                    </div>
                    <div className="text-xs text-slate-400 font-mono">
                      共计注册 <span className="text-emerald-400 font-bold">{settingsLeagues.length}</span> 个联赛 (
                      <span className="text-emerald-400">
                        {settingsLeagues.filter((l) => l.active).length}
                      </span>{" "}
                      活跃中)
                    </div>
                  </div>

                  {/* Leagues Table */}
                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-900/80 text-slate-400 font-mono">
                        <tr>
                          <th className="py-2.5 px-3">联赛标识 (ID)</th>
                          <th className="py-2.5 px-3">联赛全称与本地化</th>
                          <th className="py-2.5 px-3">国家/地区</th>
                          <th className="py-2.5 px-3">历史赛事样本</th>
                          <th className="py-2.5 px-3">量化模型</th>
                          <th className="py-2.5 px-3">状态</th>
                          <th className="py-2.5 px-3 text-right">管理操作</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono">
                        {settingsLeagues
                          .filter((l) => {
                            if (!leagueSearchQuery.trim()) return true;
                            const q = leagueSearchQuery.toLowerCase();
                            return (
                              l.id.toLowerCase().includes(q) ||
                              l.name.toLowerCase().includes(q) ||
                              (l.country && l.country.toLowerCase().includes(q))
                            );
                          })
                          .map((league) => (
                            <tr key={league.id} className="hover:bg-slate-900/40 transition">
                              <td className="py-3 px-3">
                                <span className="px-2 py-1 rounded bg-slate-800/80 text-white font-bold border border-slate-700">
                                  {league.id}
                                </span>
                              </td>
                              <td className="py-3 px-3 font-sans text-white font-medium">
                                {formatLeagueLabel(league.id, league.name)}
                              </td>
                              <td className="py-3 px-3 text-slate-400 font-sans">{league.country || "—"}</td>
                              <td className="py-3 px-3">
                                <span className="text-slate-300 font-bold">{league.matches_count}</span>
                                <span className="text-slate-500 text-[10px] ml-1">场</span>
                              </td>
                              <td className="py-3 px-3">
                                {league.has_model ? (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                    <Brain className="w-3 h-3 mr-1" /> 已就绪
                                  </span>
                                ) : (
                                  <span className="text-slate-500 text-[10px]">待训练</span>
                                )}
                              </td>
                              <td className="py-3 px-3">
                                {league.active ? (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>
                                    运行中
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/20">
                                    已停用
                                  </span>
                                )}
                              </td>
                              <td className="py-3 px-3 text-right">
                                <div className="inline-flex items-center space-x-2">
                                  <button
                                    onClick={() => handleToggleLeagueActive(league.id, league.active)}
                                    className={`px-2.5 py-1 rounded text-[11px] font-bold border transition flex items-center ${
                                      league.active
                                        ? "bg-amber-500/10 hover:bg-amber-500/20 text-amber-400 border-amber-500/30"
                                        : "bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                                    }`}
                                    title={league.active ? "停用该联赛" : "启用该联赛"}
                                  >
                                    <Power className="w-3 h-3 mr-1" />
                                    {league.active ? "停用" : "启用"}
                                  </button>

                                  <button
                                    onClick={() => handleDeleteLeague(league.id, league.name, league.matches_count)}
                                    disabled={league.matches_count > 0}
                                    className={`p-1.5 rounded text-xs border transition ${
                                      league.matches_count > 0
                                        ? "bg-slate-900/50 text-slate-600 border-slate-800 cursor-not-allowed"
                                        : "bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border-rose-500/30"
                                    }`}
                                    title={
                                      league.matches_count > 0
                                        ? "已有历史比赛记录，禁止删除"
                                        : "删除此联赛"
                                    }
                                  >
                                    <Trash2 className="w-3.5 h-3.5" />
                                  </button>
                                </div>
                              </td>
                            </tr>
                          ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {/* SUBTAB 2: TEAM ALIASES HUB */}
            {settingsSubTab === "aliases" && (
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                      <Link2 className="w-5 h-5 text-emerald-400" />
                      <span>全局球队别名字典映射库 (Team Alias Mapping Hub)</span>
                    </h2>
                    <p className="text-xs text-slate-400 mt-1">
                      统一管理各数据源（Football-Data、The Odds API、第三方盘口及历史 CSV）中使用的球队别名与官方标准球队 (Canonical Team) 的绑定关系。
                    </p>
                  </div>

                  <div className="flex items-center space-x-3">
                    <button
                      onClick={() => setShowAddAlias(!showAddAlias)}
                      className={`inline-flex items-center px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg ${
                        showAddAlias
                          ? "bg-slate-700 text-white"
                          : "bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-emerald-500/20"
                      }`}
                    >
                      <Plus className="w-4 h-4 mr-1.5" />
                      {showAddAlias ? "收起表单" : "绑定新别名"}
                    </button>

                    <button
                      onClick={() => fetchAliasesData(aliasSearch)}
                      disabled={loadingAliases}
                      className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                      title="刷新别名"
                    >
                      <RefreshCw className={`w-4 h-4 ${loadingAliases ? "animate-spin text-emerald-400" : ""}`} />
                    </button>
                  </div>
                </div>

                {/* Form: Add Alias */}
                {showAddAlias && (
                  <form onSubmit={handleCreateAlias} className="p-5 rounded-xl bg-slate-900/90 border border-emerald-500/30 grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        映射至标准官方球队 <span className="text-rose-400">*</span>
                      </label>
                      <input
                        list="teams-datalist"
                        type="text"
                        placeholder="输入球队 ID (如 arsenal, manchester-city)"
                        value={newAliasTeamId}
                        onChange={(e) => setNewAliasTeamId(e.target.value.toLowerCase().trim())}
                        required
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                      />
                      <datalist id="teams-datalist">
                        {teams.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.canonical_name} ({t.id})
                          </option>
                        ))}
                      </datalist>
                      <span className="text-[10px] text-slate-400 mt-1 block">可输入球队代码或从已有球队下拉提示中选取</span>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1">
                        第三方别名文本 (External Alias) <span className="text-rose-400">*</span>
                      </label>
                      <input
                        type="text"
                        placeholder="如: Man City, 曼城, Vissel Kobe"
                        value={newAliasName}
                        onChange={(e) => setNewAliasName(e.target.value)}
                        required
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-500"
                      />
                      <span className="text-[10px] text-slate-400 mt-1 block">外部数据源中的球队名称写法</span>
                    </div>

                    <div className="flex items-end space-x-2">
                      <button
                        type="submit"
                        disabled={creatingAlias}
                        className="w-full py-2 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                      >
                        {creatingAlias ? "正在绑定..." : "确认绑定别名"}
                      </button>
                      <button
                        type="button"
                        onClick={() => setShowAddAlias(false)}
                        className="py-2 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs transition"
                      >
                        取消
                      </button>
                    </div>
                  </form>
                )}

                {/* Search Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="relative max-w-sm w-full">
                    <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
                    <input
                      type="text"
                      placeholder="搜索别名、官方球队名或 ID..."
                      value={aliasSearch}
                      onChange={(e) => setAliasSearch(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-xl pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-600"
                    />
                  </div>
                  <div className="text-xs text-slate-400 font-mono">
                    已加载 <span className="text-emerald-400 font-bold">{aliasesList.length}</span> 条别名匹配关系
                  </div>
                </div>

                {/* Aliases Table */}
                <div className="overflow-x-auto rounded-xl border border-slate-800">
                  <table className="w-full text-xs text-left">
                    <thead className="bg-slate-900/80 text-slate-400 font-mono">
                      <tr>
                        <th className="py-2.5 px-3">外部数据源别名 (External Alias)</th>
                        <th className="py-2.5 px-3">官方标准球队 (Canonical Team)</th>
                        <th className="py-2.5 px-3">球队代号 (Team ID)</th>
                        <th className="py-2.5 px-3">来源通道</th>
                        <th className="py-2.5 px-3">国家</th>
                        <th className="py-2.5 px-3 text-right">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800 font-mono">
                      {aliasesList.map((a) => (
                        <tr key={a.id} className="hover:bg-slate-900/40 transition">
                          <td className="py-2.5 px-3 font-bold text-white">{a.external_name}</td>
                          <td className="py-2.5 px-3 text-emerald-400 font-sans font-medium">{a.canonical_name}</td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-[11px]">
                              {a.team_id}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px]">
                              {a.source_name}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 text-slate-400 font-sans">{a.country || "—"}</td>
                          <td className="py-2.5 px-3 text-right">
                            <button
                              onClick={() => handleDeleteAlias(a.id, a.external_name)}
                              className="p-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 transition text-[11px]"
                              title="解绑此别名"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                      {aliasesList.length === 0 && (
                        <tr>
                          <td colSpan={6} className="py-8 text-center text-slate-500">
                            未找到符合条件的别名映射记录
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* SUBTAB 3: QUANT RISK & HYPERPARAMETERS */}
            {settingsSubTab === "quant_risk" && (
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <Sliders className="w-5 h-5 text-indigo-400" />
                    <span>全局量化模型超参数与风控调节 (Quant Risk Control)</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    动态调整双变量泊松模型时间衰减衰减率、凯利头寸系数及 +EV 专家信号生成门槛。更新后立即在后台定价引擎与会员扫描中心全局生效。
                  </p>
                </div>

                <form onSubmit={handleSaveQuantConfig} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Value Scanner Min EV */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-bold text-slate-200">
                          +EV 正期望值预警过滤门槛 (Min EV Threshold)
                        </label>
                        <span className="text-sm font-mono font-bold text-emerald-400">
                          +{(quantConfig.value_scanner_min_ev * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        过滤边际收益过低的市场噪音，仅将期望值大于该阈值的机会推入每日精选与扫描器。
                      </p>
                      <input
                        type="range"
                        min="0.01"
                        max="0.20"
                        step="0.005"
                        value={quantConfig.value_scanner_min_ev}
                        onChange={(e) =>
                          setQuantConfig({ ...quantConfig, value_scanner_min_ev: parseFloat(e.target.value) })
                        }
                        className="w-full accent-emerald-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>+1.0% (宽松)</span>
                        <span>+5.0% (默认基准)</span>
                        <span>+20.0% (极度严格)</span>
                      </div>
                    </div>

                    {/* Kelly Fraction */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-bold text-slate-200">
                          凯利准则建议倍数 (Kelly Staking Multiplier)
                        </label>
                        <span className="text-sm font-mono font-bold text-amber-400">
                          {quantConfig.kelly_fraction}×
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        分式凯利控制资金回撤与波动率。量化学术界公认半凯利具有最优复利收益与破产隔离特性。
                      </p>
                      <CustomSelect
                        value={String(quantConfig.kelly_fraction)}
                        onChange={(val) =>
                          setQuantConfig({ ...quantConfig, kelly_fraction: parseFloat(val) })
                        }
                        buttonClassName="bg-slate-950 border-slate-700 text-xs focus:border-amber-500"
                        options={[
                          { value: "0.25", label: "0.25× - 保守四分之一凯利 (Quarter Kelly - 追求低波动与极度稳健)" },
                          { value: "0.5", label: "0.50× - 标准半凯利 (Half Kelly - 工业级默认推荐策略)" },
                          { value: "1.0", label: "1.00× - 理论全凯利 (Full Kelly - 理论最大对数资产增长率，承受高方差)" },
                        ]}
                      />
                    </div>

                    {/* Max Stake Cap */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-bold text-slate-200">
                          单场下注上限风控硬顶 (Single Bet Max Stake Cap)
                        </label>
                        <span className="text-sm font-mono font-bold text-blue-400">
                          {(quantConfig.max_stake_cap * 100).toFixed(1)}%
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        无论模型计算出的理论凯利注额多大，单场注额绝不允许超过总本金的该硬约束比例。
                      </p>
                      <input
                        type="range"
                        min="0.01"
                        max="0.15"
                        step="0.005"
                        value={quantConfig.max_stake_cap}
                        onChange={(e) =>
                          setQuantConfig({ ...quantConfig, max_stake_cap: parseFloat(e.target.value) })
                        }
                        className="w-full accent-blue-500 cursor-pointer"
                      />
                      <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                        <span>1.0% (极致风控)</span>
                        <span>5.0% (标准上限)</span>
                        <span>15.0% (激进)</span>
                      </div>
                    </div>

                    {/* Dixon-Coles Decay Xi */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <div className="flex items-center justify-between">
                        <label className="text-xs font-bold text-slate-200">
                          Dixon-Coles 历史时间衰减率 (ξ Decay Rate)
                        </label>
                        <span className="text-sm font-mono font-bold text-indigo-400">
                          ξ = {quantConfig.dixon_coles_decay_xi}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        每天历史赛事权重的指数衰减系数。当前对应时间半衰期约为{" "}
                        <span className="text-white font-bold font-mono">
                          {quantConfig.dixon_coles_decay_xi > 0
                            ? Math.round(0.693147 / quantConfig.dixon_coles_decay_xi)
                            : 385}
                        </span>{" "}
                        天。
                      </p>
                      <input
                        type="number"
                        step="0.0001"
                        min="0.0001"
                        max="0.0100"
                        value={quantConfig.dixon_coles_decay_xi}
                        onChange={(e) =>
                          setQuantConfig({ ...quantConfig, dixon_coles_decay_xi: parseFloat(e.target.value) })
                        }
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-indigo-500"
                      />
                    </div>
                  </div>

                  <div className="flex justify-end pt-4 border-t border-slate-800">
                    <button
                      type="submit"
                      disabled={savingQuant}
                      className="px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center space-x-2"
                    >
                      <Check className="w-4 h-4" />
                      <span>{savingQuant ? "正在保存..." : "保存量化风控参数"}</span>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* SUBTAB 4: DATA PROVIDER & QUOTA */}
            {settingsSubTab === "provider" && (
              <div className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  {/* Provider Configuration */}
                  <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-5">
                    <div>
                      <h2 className="text-base font-bold text-white flex items-center space-x-2">
                        <Activity className="w-5 h-5 text-emerald-400" />
                        <span>The Odds API 行情连接配置</span>
                      </h2>
                      <p className="text-xs text-slate-400 mt-1">
                        配置全球顶级博彩商赔率行情源密钥与核心参考机构（Sharp Bookmakers）。
                      </p>
                    </div>

                    <form onSubmit={handleSaveProviderConfig} className="space-y-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          The Odds API 密钥 (API Key)
                        </label>
                        <input
                          type="password"
                          placeholder={providerConfig.the_odds_api_key_masked || "在此输入新的 API Key..."}
                          value={providerConfig.the_odds_api_key || ""}
                          onChange={(e) =>
                            setProviderConfig({ ...providerConfig, the_odds_api_key: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                        />
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          状态: {providerConfig.is_key_configured ? "已在系统持久化保存" : "尚未配置"}
                        </span>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          盘口轮询间隔 (小时)
                        </label>
                        <input
                          type="number"
                          min="1"
                          max="24"
                          value={providerConfig.polling_interval_hours || 4}
                          onChange={(e) =>
                            setProviderConfig({
                              ...providerConfig,
                              polling_interval_hours: parseInt(e.target.value) || 4,
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      <div className="pt-2">
                        <button
                          type="submit"
                          disabled={savingProvider}
                          className="w-full py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50"
                        >
                          {savingProvider ? "正在保存..." : "更新行情源配置"}
                        </button>
                      </div>
                    </form>
                  </div>

                  {/* Quota Health Monitor */}
                  <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-5">
                    <div className="flex items-center justify-between">
                      <div>
                        <h2 className="text-base font-bold text-white flex items-center space-x-2">
                          <Shield className="w-5 h-5 text-blue-400" />
                          <span>实时配额与连通性监控</span>
                        </h2>
                        <p className="text-xs text-slate-400 mt-1">
                          实时检测行情源在线状态与本月剩余可用请求配额。
                        </p>
                      </div>
                      <button
                        onClick={handleCheckQuota}
                        disabled={checkingQuota}
                        className="px-3 py-1.5 rounded-lg bg-blue-500/10 hover:bg-blue-500/20 border border-blue-500/30 text-blue-400 text-xs font-bold transition flex items-center space-x-1"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${checkingQuota ? "animate-spin" : ""}`} />
                        <span>检测连通性</span>
                      </button>
                    </div>

                    <div className="space-y-4">
                      {quotaStatus ? (
                        <div className="p-4 rounded-xl bg-slate-900/90 border border-slate-800 space-y-3 font-mono">
                          <div className="flex items-center justify-between">
                            <span className="text-xs text-slate-400">服务状态:</span>
                            <span
                              className={`px-2.5 py-0.5 rounded text-[11px] font-bold ${
                                quotaStatus.status === "HEALTHY"
                                  ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                  : "bg-rose-500/10 text-rose-400 border border-rose-500/20"
                              }`}
                            >
                              {quotaStatus.status}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-xs text-slate-400">本月剩余可用请求:</span>
                            <span className="text-base font-bold text-white">
                              {quotaStatus.requests_remaining !== null ? quotaStatus.requests_remaining : "未知"}
                            </span>
                          </div>

                          <div className="flex items-center justify-between">
                            <span className="text-xs text-slate-400">本月已消耗请求:</span>
                            <span className="text-xs text-slate-300">
                              {quotaStatus.requests_used !== null ? quotaStatus.requests_used : "未知"}
                            </span>
                          </div>

                          <div className="p-2.5 rounded-lg bg-slate-950 text-slate-400 text-[11px] font-sans">
                            {quotaStatus.message}
                          </div>
                        </div>
                      ) : (
                        <div className="p-8 rounded-xl bg-slate-900/40 border border-dashed border-slate-800 text-center text-slate-500 text-xs">
                          点击上方“检测连通性”按钮以获取最新的 API 握手与配额余量。
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* SUBTAB 5: MONETIZATION & PRICING */}
            {settingsSubTab === "monetization" && (
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <Coins className="w-5 h-5 text-amber-400" />
                    <span>商业化体系、订阅定价与拉新策略 (Monetization Policy)</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    配置 Analyst 专家会籍价格、新用户注册免试用期天数以及接受的加密货币结算方式。
                  </p>
                </div>

                <form onSubmit={handleSaveMonetizationConfig} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {/* Monthly Price */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <label className="block text-xs font-bold text-slate-200">
                        Analyst 专家月费 (USD / 30天)
                      </label>
                      <div className="relative">
                        <span className="absolute left-3 top-2 text-slate-500 font-mono text-xs">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="1"
                          max="1000"
                          value={monetizationConfig.monthly_price_usd}
                          onChange={(e) =>
                            setMonetizationConfig({
                              ...monetizationConfig,
                              monthly_price_usd: parseFloat(e.target.value) || 29.0,
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-7 pr-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 block">默认标准定价: $29.00 USD</span>
                    </div>

                    {/* Season Price */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <label className="block text-xs font-bold text-slate-200">
                        Analyst 专家赛季费 (USD / 270天)
                      </label>
                      <div className="relative">
                        <span className="absolute left-3 top-2 text-slate-500 font-mono text-xs">$</span>
                        <input
                          type="number"
                          step="0.01"
                          min="1"
                          max="5000"
                          value={monetizationConfig.season_price_usd}
                          onChange={(e) =>
                            setMonetizationConfig({
                              ...monetizationConfig,
                              season_price_usd: parseFloat(e.target.value) || 149.0,
                            })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg pl-7 pr-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                        />
                      </div>
                      <span className="text-[10px] text-slate-500 block">默认标准定价: $149.00 USD</span>
                    </div>

                    {/* New User Free Trial Days */}
                    <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                      <label className="block text-xs font-bold text-slate-200">
                        新用户注册赠送体验天数
                      </label>
                      <input
                        type="number"
                        min="0"
                        max="30"
                        value={monetizationConfig.new_user_trial_days}
                        onChange={(e) =>
                          setMonetizationConfig({
                            ...monetizationConfig,
                            new_user_trial_days: parseInt(e.target.value) || 0,
                          })
                        }
                        className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-amber-500"
                      />
                      <span className="text-[10px] text-slate-500 block">
                        设为 0 表示不赠送；设为 3 或 7 表示注册即享专家权限进行拉新试用
                      </span>
                    </div>
                  </div>

                  <div className="flex justify-end pt-4 border-t border-slate-800">
                    <button
                      type="submit"
                      disabled={savingMonetization}
                      className="px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center space-x-2"
                    >
                      <Check className="w-4 h-4" />
                      <span>{savingMonetization ? "正在保存..." : "保存商业化策略"}</span>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* SUBTAB 6: NOTIFICATIONS & WEBHOOKS */}
            {settingsSubTab === "notifications" && (
              <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white flex items-center space-x-2">
                    <Bell className="w-5 h-5 text-blue-400" />
                    <span>即时通讯推送与 Webhook 集成 (Notifications & Webhooks)</span>
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    配置 Telegram VIP 频道的自动推单机器人与第三方 Webhook 回调。当扫描到超额高期望值机会（+EV）时将自动触发即时消息广播。
                  </p>
                </div>

                <form onSubmit={handleSaveNotifConfig} className="space-y-6">
                  <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Telegram Config */}
                    <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                        <span className="text-xs font-bold text-white flex items-center">
                          <Send className="w-4 h-4 mr-1.5 text-blue-400" />
                          Telegram Bot 频道广播配置
                        </span>
                        <label className="flex items-center space-x-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={notifConfig.telegram_enabled}
                            onChange={(e) =>
                              setNotifConfig({ ...notifConfig, telegram_enabled: e.target.checked })
                            }
                            className="rounded border-slate-700 text-blue-500 bg-slate-950"
                          />
                          <span className="text-xs text-slate-300">开启广播</span>
                        </label>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          Telegram Bot Token
                        </label>
                        <input
                          type="password"
                          placeholder={notifConfig.telegram_bot_token_masked || "bot123456:ABC-DEF..."}
                          value={notifConfig.telegram_bot_token || ""}
                          onChange={(e) =>
                            setNotifConfig({ ...notifConfig, telegram_bot_token: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          目标 Channel ID 或 Group ID
                        </label>
                        <input
                          type="text"
                          placeholder="如: @matchlambda_vip 或 -10012345678"
                          value={notifConfig.telegram_channel_id || ""}
                          onChange={(e) =>
                            setNotifConfig({ ...notifConfig, telegram_channel_id: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-blue-500"
                        />
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          自动触发推送的最小 +EV 阈值: {(notifConfig.telegram_min_ev * 100).toFixed(1)}%
                        </label>
                        <input
                          type="range"
                          min="0.03"
                          max="0.20"
                          step="0.005"
                          value={notifConfig.telegram_min_ev}
                          onChange={(e) =>
                            setNotifConfig({ ...notifConfig, telegram_min_ev: parseFloat(e.target.value) })
                          }
                          className="w-full accent-blue-500 cursor-pointer"
                        />
                      </div>
                    </div>

                    {/* Generic Webhook Config */}
                    <div className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4">
                      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                        <span className="text-xs font-bold text-white flex items-center">
                          <Activity className="w-4 h-4 mr-1.5 text-emerald-400" />
                          通用 Webhook 回调集成
                        </span>
                        <label className="flex items-center space-x-2 cursor-pointer">
                          <input
                            type="checkbox"
                            checked={notifConfig.webhook_enabled}
                            onChange={(e) =>
                              setNotifConfig({ ...notifConfig, webhook_enabled: e.target.checked })
                            }
                            className="rounded border-slate-700 text-emerald-500 bg-slate-950"
                          />
                          <span className="text-xs text-slate-300">开启 Webhook</span>
                        </label>
                      </div>

                      <div>
                        <label className="block text-xs font-semibold text-slate-300 mb-1">
                          Webhook POST URL
                        </label>
                        <input
                          type="url"
                          placeholder="https://your-server.com/api/webhook"
                          value={notifConfig.webhook_url || ""}
                          onChange={(e) =>
                            setNotifConfig({ ...notifConfig, webhook_url: e.target.value })
                          }
                          className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono text-white focus:outline-none focus:border-emerald-500"
                        />
                        <span className="text-[10px] text-slate-500 mt-1 block">
                          支持接收包含高置信度机会、支付成功与系统异常的 JSON Payload
                        </span>
                      </div>

                      {/* Test Notification Results */}
                      {testNotifResult && (
                        <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono space-y-1">
                          <div className="text-slate-400 font-bold mb-1">测试广播发送结果:</div>
                          {Object.entries(testNotifResult).map(([ch, r]: [string, any]) => (
                            <div key={ch} className="flex items-center justify-between">
                              <span className="uppercase text-slate-300">{ch}:</span>
                              <span
                                className={
                                  r.status === "SUCCESS"
                                    ? "text-emerald-400"
                                    : r.status === "SKIPPED"
                                    ? "text-slate-500"
                                    : "text-rose-400"
                                }
                              >
                                {r.status} ({r.detail})
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => handleTestNotif("all")}
                      disabled={testingNotif}
                      className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-bold transition flex items-center space-x-1.5"
                    >
                      <Send className="w-3.5 h-3.5 text-blue-400" />
                      <span>{testingNotif ? "正在发送测试..." : "发送测试广播 (Test Ping)"}</span>
                    </button>

                    <button
                      type="submit"
                      disabled={savingNotif}
                      className="px-6 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition shadow-lg shadow-emerald-500/20 disabled:opacity-50 flex items-center space-x-2"
                    >
                      <Check className="w-4 h-4" />
                      <span>{savingNotif ? "正在保存..." : "保存通知配置"}</span>
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* SUBTAB 7: AUDIT LOGS & CACHE */}
            {settingsSubTab === "audit_cache" && (
              <div className="space-y-6">
                {/* Cache Management Card */}
                <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                  <div>
                    <h2 className="text-base font-bold text-white flex items-center space-x-2">
                      <RefreshCw className="w-5 h-5 text-indigo-400" />
                      <span>Redis 缓存治理与预测预热 (Cache Purge)</span>
                    </h2>
                    <p className="text-xs text-slate-400 mt-1">
                      大规模历史数据补录或量化模型重新拟合后，可一键清空所有热点预测缓存并重新计算最新公允赔率。
                    </p>
                  </div>
                  <button
                    onClick={handlePurgeCache}
                    disabled={purgingCache}
                    className="px-5 py-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 text-rose-300 text-xs font-bold transition flex items-center space-x-1.5 shrink-0"
                  >
                    <Trash2 className="w-4 h-4" />
                    <span>{purgingCache ? "正在清理..." : "一键清理系统缓存 (Purge Cache)"}</span>
                  </button>
                </div>

                {/* Audit Logs Card */}
                <div className="bg-[#0f172a]/70 border border-slate-800/80 rounded-2xl p-6 backdrop-blur shadow-xl space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h2 className="text-base font-bold text-white flex items-center space-x-2">
                        <FileText className="w-5 h-5 text-emerald-400" />
                        <span>管理员操作审计日志 (Audit Trail)</span>
                      </h2>
                      <p className="text-xs text-slate-400 mt-1">
                        严格追踪记录系统运维变更动作（包括参数修改、别名变更、联赛创建与缓存清理等）。
                      </p>
                    </div>
                    <button
                      onClick={fetchAuditLogs}
                      disabled={loadingAudit}
                      className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                      title="刷新审计日志"
                    >
                      <RefreshCw className={`w-4 h-4 ${loadingAudit ? "animate-spin text-emerald-400" : ""}`} />
                    </button>
                  </div>

                  <div className="overflow-x-auto rounded-xl border border-slate-800">
                    <table className="w-full text-xs text-left">
                      <thead className="bg-slate-900/80 text-slate-400 font-mono">
                        <tr>
                          <th className="py-2.5 px-3">操作时间 (UTC)</th>
                          <th className="py-2.5 px-3">执行管理员</th>
                          <th className="py-2.5 px-3">操作指令 (Action)</th>
                          <th className="py-2.5 px-3">目标对象 (Target)</th>
                          <th className="py-2.5 px-3">详情记录</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 font-mono">
                        {auditLogs.map((log) => (
                          <tr key={log.id} className="hover:bg-slate-900/40 transition">
                            <td className="py-2.5 px-3 text-slate-400">
                              {safeSlice(log.created_at, 0, 19).replace("T", " ")}
                            </td>
                            <td className="py-2.5 px-3 text-white font-medium">{log.admin_email}</td>
                            <td className="py-2.5 px-3">
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                                {log.action}
                              </span>
                            </td>
                            <td className="py-2.5 px-3 text-emerald-400 font-medium">{log.target || "—"}</td>
                            <td className="py-2.5 px-3 text-slate-400 text-[11px] max-w-xs truncate">
                              {JSON.stringify(log.details)}
                            </td>
                          </tr>
                        ))}
                        {auditLogs.length === 0 && (
                          <tr>
                            <td colSpan={5} className="py-8 text-center text-slate-500">
                              暂无审计操作日志记录
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
