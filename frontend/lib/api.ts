const TOKEN_STORAGE_KEY = "matchlambda_auth_token";
export const AUTH_CLEARED_EVENT = "auth:cleared";

let memoryToken: string | null = null;
let memoryInitialized = false;

function readStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function dispatchAuthCleared() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(AUTH_CLEARED_EVENT));
}

if (typeof window !== "undefined") {
  const flag = "__matchlambdaAuthStorageBound";
  const root = window as Window & { [flag]?: boolean };
  if (!root[flag]) {
    root[flag] = true;
    window.addEventListener("storage", (event) => {
      if (event.key !== TOKEN_STORAGE_KEY && event.key !== null) return;
      memoryInitialized = true;
      if (event.key === null || event.newValue == null) {
        memoryToken = null;
        dispatchAuthCleared();
        return;
      }
      memoryToken = event.newValue;
    });
  }
}

/**
 * Persist the token to localStorage so it survives a page refresh.
 * After the first read, the in-memory cache is authoritative. The storage
 * listener keeps it aligned with other tabs, including a logout (null).
 *
 * SECURITY NOTE: localStorage is readable by any script running on this origin,
 * so a successful XSS could exfiltrate the bearer token. The CSP in
 * next.config.js (no `unsafe-eval`, exact `connect-src`) reduces that surface
 * but does not eliminate it. The durable fix is to move the session to an
 * httpOnly, Secure, SameSite cookie issued by the backend and stop sending the
 * token from JS; this file intentionally keeps the existing flow until that
 * backend change lands, because switching unilaterally would break login.
 */
export const setAuthToken = (token: string | null) => {
  memoryToken = token;
  memoryInitialized = true;
  if (typeof window !== "undefined") {
    try {
      if (token) {
        window.localStorage.setItem(TOKEN_STORAGE_KEY, token);
      } else {
        window.localStorage.removeItem(TOKEN_STORAGE_KEY);
      }
    } catch {
      // localStorage unavailable (e.g. private mode); keep in-memory only
    }
    if (!token) dispatchAuthCleared();
  }
};

export const getAuthToken = (): string | null => {
  if (memoryInitialized) return memoryToken;
  memoryToken = readStoredToken();
  memoryInitialized = true;
  return memoryToken;
};

export interface ApiError {
  code: string;
  message: string;
}

export function getApiBase(): string {
  const configured = process.env.NEXT_PUBLIC_API_URL;
  if (configured) return configured;
  if (typeof window !== "undefined") {
    if (window.location.protocol === "https:") {
      return `${window.location.origin}/v1`;
    }
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000/v1`;
  }
  return "http://127.0.0.1:8000/v1";
}

/** Build-time override only. Request code should call getApiBase(). */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export interface RequestOptions extends RequestInit {
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 60_000;

export function isAbortError(err: unknown): boolean {
  if (!err) return false;
  if (typeof DOMException !== "undefined" && err instanceof DOMException) {
    return err.name === "AbortError" || err.code === 20;
  }
  if (err instanceof Error) {
    return err.name === "AbortError" || err.message.toLowerCase().includes("aborted");
  }
  return false;
}

export function isApiError(err: unknown): err is ApiError {
  return (
    typeof err === "object" &&
    err !== null &&
    "code" in err &&
    typeof (err as any).code === "string" &&
    "message" in err &&
    typeof (err as any).message === "string"
  );
}

export async function apiRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (typeof FormData !== "undefined" && options.body instanceof FormData) {
    // Let browser set multipart/form-data boundary automatically
  } else if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const token = getAuthToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort(new Error("Request timed out."));
  }, timeoutMs);

  const callerSignal = options.signal;
  const onCallerAbort = () => {
    controller.abort(callerSignal?.reason || new Error("Request cancelled."));
  };
  if (callerSignal) {
    if (callerSignal.aborted) {
      controller.abort(callerSignal.reason || new Error("Request cancelled."));
    } else {
      callerSignal.addEventListener("abort", onCallerAbort);
    }
  }

  const url = `${getApiBase()}${endpoint}`;

  try {
    const response = await fetch(url, {
      ...options,
      headers,
      signal: controller.signal,
    });

    let data: any = null;
    try {
      data = await response.json();
    } catch {
      const empty =
        response.status === 204 || response.headers.get("content-length") === "0";
      if (empty) {
        if (!response.ok) {
          if (response.status === 401) setAuthToken(null);
          const error: ApiError = {
            code: "UNKNOWN_ERROR",
            message: `Request failed with status ${response.status}`,
          };
          throw error;
        }
        return undefined as T;
      }
      data = null;
    }

    if (!response.ok) {
      if (response.status === 401) setAuthToken(null);
      const error: ApiError = data?.error || {
        code: "UNKNOWN_ERROR",
        message: `Request failed with status ${response.status}`,
      };
      throw error;
    }

    return data as T;
  } catch (err) {
    if (isApiError(err)) {
      throw err;
    }
    if (timedOut) {
      const error: ApiError = { code: "TIMEOUT", message: "请求处理超时，请稍后重试。" };
      throw error;
    }
    if (callerSignal?.aborted || isAbortError(err)) {
      const error: ApiError = { code: "ABORTED", message: "Request was cancelled." };
      throw error;
    }
    throw err;
  } finally {
    clearTimeout(timeoutId);
    if (callerSignal) callerSignal.removeEventListener("abort", onCallerAbort);
  }
}
