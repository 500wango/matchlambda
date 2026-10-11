"use client";

import Link from "next/link";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main
      id="main-content"
      className="min-h-screen bg-[#080c14] text-slate-100 flex flex-col items-center justify-center p-6 space-y-6"
    >
      <Link
        href="/"
        className="flex items-center space-x-2.5 group cursor-pointer hover:opacity-95 transition"
        title="返回首页"
      >
        <div className="h-9 w-9 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-lg text-white shadow-lg shadow-blue-500/20 group-hover:bg-blue-500 transition">
          λ
        </div>
        <span className="font-extrabold text-xl tracking-tight text-white group-hover:text-blue-300 transition">
          MatchLambda
        </span>
      </Link>

      <div className="max-w-md text-center space-y-4 bg-[#0d121f] border border-slate-800 p-6 rounded-2xl shadow-xl">
        <h1 className="text-xl font-bold text-white">Something went wrong</h1>
        <p className="text-sm text-slate-400">
          {error?.message || "An unexpected error occurred."}
        </p>
        <div className="flex items-center justify-center space-x-3 pt-2">
          <button
            type="button"
            onClick={() => reset()}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm font-semibold transition"
          >
            Try again
          </button>
          <Link
            href="/"
            className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-semibold transition"
          >
            Back to Home
          </Link>
        </div>
      </div>
    </main>
  );
}
