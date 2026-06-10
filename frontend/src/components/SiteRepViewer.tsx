"use client";

import { useEffect, useState } from "react";
import { getSitRep } from "@/lib/api";
import type { SitRep, ThreatTier } from "@/lib/types";

const TIER_BADGE: Record<ThreatTier, string> = {
  WATCH:     "bg-yellow-500/20 text-yellow-300 border border-yellow-500/40",
  ALERT:     "bg-orange-500/20 text-orange-300 border border-orange-500/40",
  EMERGENCY: "bg-red-500/20 text-red-300 border border-red-500/40",
  NORMAL:    "bg-gray-500/20 text-gray-300 border border-gray-500/40",
};

interface SitRepViewerProps {
  sitrepId?: string;
  sitrep?: SitRep;
}

export default function SitRepViewer({ sitrepId, sitrep: propSitrep }: SitRepViewerProps) {
  const [sitrep, setSitrep] = useState<SitRep | null>(propSitrep ?? null);
  const [loading, setLoading] = useState(false);
  const [section, setSection] = useState<"overview" | "epi" | "env" | "actions">("overview");

  useEffect(() => {
    if (propSitrep) { setSitrep(propSitrep); return; }
    if (!sitrepId) return;
    setLoading(true);
    getSitRep(sitrepId)
      .then(setSitrep)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [sitrepId, propSitrep]);

  if (loading) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-700 p-6 animate-pulse">
        <div className="h-4 bg-gray-700 rounded w-1/3 mb-3" />
        <div className="h-3 bg-gray-800 rounded w-full mb-2" />
        <div className="h-3 bg-gray-800 rounded w-4/5" />
      </div>
    );
  }

  if (!sitrep) {
    return (
      <div className="bg-gray-900 rounded-xl border border-gray-700 p-6 text-center text-gray-500 text-sm">
        No situation report available yet.
        <div className="text-xs mt-1">Run the pipeline at ALERT or EMERGENCY tier to generate one.</div>
      </div>
    );
  }

  const tier = sitrep.threat_tier as ThreatTier;
  const SECTIONS = [
    { key: "overview", label: "Overview" },
    { key: "epi",      label: "Epidemiology" },
    { key: "env",      label: "Environment" },
    { key: "actions",  label: "Actions" },
  ] as const;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-800 flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${TIER_BADGE[tier]}`}>
              {tier}
            </span>
            <span className="text-xs text-gray-500 uppercase tracking-wide">WHO-Style SitRep</span>
          </div>
          <p className="text-sm text-gray-200 leading-snug font-medium">
            {sitrep.report.executive_summary}
          </p>
        </div>
        <div className="text-xs text-gray-600 whitespace-nowrap flex-shrink-0">
          {new Date(sitrep.generated_at).toLocaleDateString("en-GB", {
            day: "2-digit", month: "short", year: "numeric",
          })}
        </div>
      </div>

      {/* Section tabs */}
      <div className="flex border-b border-gray-800">
        {SECTIONS.map(({ key, label }) => (
          <button
            key={key}
            onClick={() => setSection(key)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
              section === key
                ? "text-white border-b-2 border-blue-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Section content */}
      <div className="p-4 text-sm text-gray-300 leading-relaxed space-y-3 min-h-32">
        {section === "overview" && (
          <>
            <p>{sitrep.report.situation_overview}</p>
            <div className="mt-2 pt-2 border-t border-gray-800 text-xs text-gray-500">
              <span className="font-medium text-gray-400">Surveillance gaps: </span>
              {sitrep.report.surveillance_gaps?.join(" · ") || "None noted"}
            </div>
          </>
        )}
        {section === "epi" && <p>{sitrep.report.epidemiological_analysis}</p>}
        {section === "env" && <p>{sitrep.report.environmental_context}</p>}
        {section === "actions" && (
          <ol className="space-y-2">
            {sitrep.report.recommended_actions?.map((action, i) => (
              <li key={i} className="flex gap-2">
                <span className="text-blue-400 font-bold flex-shrink-0">{i + 1}.</span>
                <span>{action}</span>
              </li>
            ))}
          </ol>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 bg-gray-950 border-t border-gray-800 text-xs text-gray-600 flex justify-between">
        <span>Status: {sitrep.status}</span>
        <span className="text-yellow-700">
          ⚠ Requires epidemiologist review before action
        </span>
      </div>
    </div>
  );
}