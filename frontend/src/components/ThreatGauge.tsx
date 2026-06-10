"use client";

import { useEffect, useRef } from "react";
import type { ThreatTier } from "@/lib/types";

const TIER_CONFIG = {
  NORMAL:    { angle: -120, color: "#6b7280", label: "NORMAL",    score: 0  },
  WATCH:     { angle:  -40, color: "#eab308", label: "WATCH",     score: 38 },
  ALERT:     { angle:   20, color: "#f97316", label: "ALERT",     score: 62 },
  EMERGENCY: { angle:  100, color: "#ef4444", label: "EMERGENCY", score: 87 },
};

interface ThreatGaugeProps {
  tier: ThreatTier | "NORMAL";
  score?: number;
  confidence?: number;
  animating?: boolean;
}

export default function ThreatGauge({
  tier = "NORMAL",
  score,
  confidence,
  animating = false,
}: ThreatGaugeProps) {
  const needleRef = useRef<SVGLineElement>(null);
  const glowRef = useRef<SVGCircleElement>(null);
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG.NORMAL;

  // Animate needle to target angle
  useEffect(() => {
    if (!needleRef.current) return;
    const target = config.angle;
    needleRef.current.style.transition = "transform 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)";
    needleRef.current.style.transform = `rotate(${target}deg)`;
    needleRef.current.style.transformOrigin = "bottom center";
  }, [tier, config.angle]);

  return (
    <div className="flex flex-col items-center select-none">
      <svg viewBox="0 0 280 180" className="w-full max-w-xs" aria-label={`Threat tier: ${tier}`}>
        {/* Background arc segments */}
        {/* Normal */}
        <path d="M 30 150 A 110 110 0 0 1 80 55"  fill="none" stroke="#374151" strokeWidth="22" strokeLinecap="round" />
        {/* Watch */}
        <path d="M 80 55 A 110 110 0 0 1 140 30" fill="none" stroke="#eab30833" strokeWidth="22" strokeLinecap="round" />
        {/* Alert */}
        <path d="M 140 30 A 110 110 0 0 1 200 55" fill="none" stroke="#f9731633" strokeWidth="22" strokeLinecap="round" />
        {/* Emergency */}
        <path d="M 200 55 A 110 110 0 0 1 250 150" fill="none" stroke="#ef444433" strokeWidth="22" strokeLinecap="round" />

        {/* Active segment highlight */}
        {tier === "WATCH" && (
          <path d="M 80 55 A 110 110 0 0 1 140 30" fill="none" stroke="#eab308" strokeWidth="22" strokeLinecap="round" />
        )}
        {tier === "ALERT" && (
          <>
            <path d="M 80 55 A 110 110 0 0 1 140 30" fill="none" stroke="#f97316aa" strokeWidth="22" strokeLinecap="round" />
            <path d="M 140 30 A 110 110 0 0 1 200 55" fill="none" stroke="#f97316" strokeWidth="22" strokeLinecap="round" />
          </>
        )}
        {tier === "EMERGENCY" && (
          <>
            <path d="M 80 55 A 110 110 0 0 1 140 30"  fill="none" stroke="#ef4444aa" strokeWidth="22" strokeLinecap="round" />
            <path d="M 140 30 A 110 110 0 0 1 200 55" fill="none" stroke="#ef4444cc" strokeWidth="22" strokeLinecap="round" />
            <path d="M 200 55 A 110 110 0 0 1 250 150" fill="none" stroke="#ef4444" strokeWidth="22" strokeLinecap="round" />
          </>
        )}

        {/* Tick marks */}
        {[-120, -80, -40, 0, 40, 80, 120].map((angle, i) => {
          const rad = (angle - 90) * (Math.PI / 180);
          const x1 = 140 + 95 * Math.cos(rad);
          const y1 = 150 + 95 * Math.sin(rad);
          const x2 = 140 + 108 * Math.cos(rad);
          const y2 = 150 + 108 * Math.sin(rad);
          return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#4b5563" strokeWidth="2" />;
        })}

        {/* Zone labels */}
        <text x="38"  y="168" fill="#6b7280" fontSize="9" textAnchor="middle">NORMAL</text>
        <text x="105" y="42"  fill="#eab308" fontSize="9" textAnchor="middle">WATCH</text>
        <text x="175" y="42"  fill="#f97316" fontSize="9" textAnchor="middle">ALERT</text>
        <text x="242" y="168" fill="#ef4444" fontSize="9" textAnchor="middle">EMRG</text>

        {/* Needle pivot glow */}
        <circle
          ref={glowRef}
          cx="140" cy="150" r="18"
          fill={config.color + "22"}
          style={{ transition: "fill 0.8s ease" }}
        />

        {/* Needle */}
        <g transform="translate(140, 150)">
          <line
            ref={needleRef}
            x1="0" y1="0" x2="0" y2="-85"
            stroke={config.color}
            strokeWidth="3"
            strokeLinecap="round"
            style={{
              transform: `rotate(${config.angle}deg)`,
              transformOrigin: "bottom center",
              transition: "transform 1.2s cubic-bezier(0.34, 1.56, 0.64, 1)",
              filter: tier === "EMERGENCY" ? `drop-shadow(0 0 6px ${config.color})` : "none",
            }}
          />
          <circle cx="0" cy="0" r="7" fill={config.color} />
          <circle cx="0" cy="0" r="3" fill="white" />
        </g>

        {/* Tier label */}
        <text
          x="140" y="138"
          fill={config.color}
          fontSize="13"
          fontWeight="700"
          textAnchor="middle"
          style={{ transition: "fill 0.5s ease" }}
        >
          {tier}
        </text>
      </svg>

      {/* Score + confidence row */}
      <div className="flex gap-6 mt-1 text-center">
        {score !== undefined && (
          <div>
            <div className="text-2xl font-bold" style={{ color: config.color }}>
              {Math.round(score)}
            </div>
            <div className="text-xs text-gray-500">composite score</div>
          </div>
        )}
        {confidence !== undefined && (
          <div>
            <div className="text-2xl font-bold text-gray-300">
              {Math.round(confidence * 100)}%
            </div>
            <div className="text-xs text-gray-500">confidence</div>
          </div>
        )}
      </div>

      {/* Animating indicator */}
      {animating && (
        <div className="mt-2 flex items-center gap-1.5 text-xs text-gray-400">
          <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
          Pipeline running…
        </div>
      )}
    </div>
  );
}
