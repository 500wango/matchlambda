"use client";

import { useEffect, useState } from "react";
import { apiRequest } from "./api";

/**
 * PRD §2.1 league gate, client side. Null means the gate is unknown or inert
 * (request failed, or no snapshot exists yet), so surfaces fall back to the
 * static league list and the backend remains the enforcement point.
 */
export const GATE_GROUP_IDS = new Set(["ALL", "TOP5", "NORDIC", "EURO_OTHER", "GLOBAL", "CUPS"]);

export function useEligibleLeagues(): Set<string> | null {
  const [ids, setIds] = useState<Set<string> | null>(null);

  useEffect(() => {
    let active = true;
    apiRequest<any[]>("/matches/leagues")
      .then((rows) => {
        if (!active || !Array.isArray(rows) || rows.length === 0) return;
        if (rows.some((row) => typeof row?.eligible !== "boolean")) return;
        setIds(new Set(rows.filter((row) => row.eligible).map((row) => String(row.id).toUpperCase())));
      })
      .catch(() => {
        // Static list stays; the server still gates every payload.
      });
    return () => {
      active = false;
    };
  }, []);

  return ids;
}

export function isLeagueVisible(id: string, eligible: Set<string> | null): boolean {
  if (!eligible) return true;
  const upper = String(id).toUpperCase();
  return GATE_GROUP_IDS.has(upper) || eligible.has(upper);
}
