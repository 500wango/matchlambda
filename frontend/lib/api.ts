let authToken: string | null = null;

export const setAuthToken = (token: string | null) => {
  authToken = token;
};

export const getAuthToken = () => authToken;

export interface ApiError {
  code: string;
  message: string;
}

export function getApiBase(): string {
  if (typeof window !== "undefined") {
    const host = window.location.hostname || "127.0.0.1";
    return `http://${host}:8000/v1`;
  }
  return process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/v1";
}

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/v1";

export async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  if (authToken) {
    headers.set("Authorization", `Bearer ${authToken}`);
  }

  const base = getApiBase();
  const url = `${base}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers,
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error: ApiError = data?.error || {
      code: "UNKNOWN_ERROR",
      message: `Request failed with status ${response.status}`,
    };
    throw error;
  }

  return data as T;
}
