"use client";

import { useMemo, useState } from "react";
import { BenchmarkResults, DOC_LABELS, DocResult } from "@/lib/types";

const DOC_ORDER = ["annual_report", "fund_doc", "ghg_scope3"];
const DOC_COLORS: Record<string, string> = {
  annual_report: "#2563eb",
  fund_doc: "#0f172a",
  ghg_scope3: "#64748b",
};

function fmtPct(v: number | null): string {
  return v === null ? "not run" : `${(v * 100).toFixed(1)}%`;
}

function fmtNum(v: number | null, digits = 0): string {
  return v === null ? "not run" : v.toFixed(digits);
}

export function OverviewClient({ data }: { data: BenchmarkResults }) {
  const [selectedDoc, setSelectedDoc] = useState<string>("all");

  const configMap = useMemo(() => {
    const m = new Map<string, { stage_changed: string | null; description: string }>();
    for (const c of data.configs) {
      m.set(c.config_id, { stage_changed: c.stage_changed, description: c.description });
    }
    return m;
  }, [data.configs]);

  const rankedRows = useMemo(() => {
    const configIds = data.configs.map((c) => c.config_id);
    if (selectedDoc !== "all") {
      return configIds
        .map((cid) => {
          const row = data.results.find((r) => r.config_id === cid && r.doc_id === selectedDoc);
          return row
            ? {
                config_id: cid,
                correctness: row.correctness,
                hit_at_5: row.hit_at_5,
                faithfulness: row.faithfulness,
                refusal_accuracy: row.refusal_accuracy,
                latency_p95_ms: row.latency_p95_ms,
                tokens_per_query: row.tokens_per_query,
                missing: false,
              }
            : {
                config_id: cid,
                correctness: null,
                hit_at_5: null,
                faithfulness: null,
                refusal_accuracy: null,
                latency_p95_ms: null,
                tokens_per_query: null,
                missing: true,
              };
        })
        .sort((a, b) => (b.correctness ?? -1) - (a.correctness ?? -1));
    }

    return configIds
      .map((cid) => {
        const rows = data.results.filter((r) => r.config_id === cid);
        if (rows.length === 0) {
          return {
            config_id: cid,
            correctness: null,
            hit_at_5: null,
            faithfulness: null,
            refusal_accuracy: null,
            latency_p95_ms: null,
            tokens_per_query: null,
            missing: true,
          };
        }
        const avg = (fn: (r: DocResult) => number) =>
          rows.reduce((acc, r) => acc + fn(r), 0) / rows.length;
        return {
          config_id: cid,
          correctness: avg((r) => r.correctness),
          hit_at_5: avg((r) => r.hit_at_5),
          faithfulness: avg((r) => r.faithfulness),
          refusal_accuracy: avg((r) => r.refusal_accuracy),
          latency_p95_ms: Math.max(...rows.map((r) => r.latency_p95_ms)),
          tokens_per_query: avg((r) => r.tokens_per_query),
          missing: false,
        };
      })
      .sort((a, b) => (b.correctness ?? -1) - (a.correctness ?? -1));
  }, [data, selectedDoc]);

  // Chart dimensions for C1 -> C7 correctness line chart
  const width = 760;
  const height = 280;
  const pad = { top: 20, right: 24, bottom: 38, left: 48 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const cfgList = data.configs.map((c) => c.config_id);

  const xFor = (idx: number) =>
    pad.left + (cfgList.length > 1 ? (idx / (cfgList.length - 1)) * innerW : innerW / 2);
  const yFor = (val: number) => pad.top + (1 - val) * innerH;

  return (
    <div>
      <h1>RAGBench Overview</h1>
      <p className="subtitle">
        7-configuration RAG ladder across 3 public PDFs (60 golden questions). All metrics read from{" "}
        <code>public/results.json</code>.
      </p>

      <div className="tabs" role="tablist" aria-label="Document filter">
        <button
          type="button"
          className={`tab-btn${selectedDoc === "all" ? " active" : ""}`}
          onClick={() => setSelectedDoc("all")}
        >
          All Docs (Mean)
        </button>
        {DOC_ORDER.map((docId) => (
          <button
            key={docId}
            type="button"
            className={`tab-btn${selectedDoc === docId ? " active" : ""}`}
            onClick={() => setSelectedDoc(docId)}
          >
            {DOC_LABELS[docId] ?? docId}
          </button>
        ))}
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>
          Ranked Configurations —{" "}
          {selectedDoc === "all" ? "All Docs (Mean)" : DOC_LABELS[selectedDoc] ?? selectedDoc}
        </h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Config</th>
                <th>Stage Changed</th>
                <th className="num">Correctness</th>
                <th className="num">Hit@5</th>
                <th className="num">Faithfulness</th>
                <th className="num">Refusal Acc</th>
                <th className="num">{selectedDoc === "all" ? "Max p95 (ms)" : "p95 (ms)"}</th>
                <th className="num">Tokens / Q</th>
              </tr>
            </thead>
            <tbody>
              {rankedRows.map((row, idx) => {
                const info = configMap.get(row.config_id);
                const isWinner =
                  selectedDoc !== "all" && data.winners?.[selectedDoc] === row.config_id;
                return (
                  <tr key={row.config_id}>
                    <td>{row.missing ? "—" : `#${idx + 1}`}</td>
                    <td>
                      <strong>{row.config_id}</strong>{" "}
                      {isWinner && <span className="badge">Winner</span>}
                    </td>
                    <td>{info?.stage_changed ?? "baseline"}</td>
                    <td className="num">
                      <strong>{fmtPct(row.correctness)}</strong>
                    </td>
                    <td className="num">{fmtPct(row.hit_at_5)}</td>
                    <td className="num">{fmtPct(row.faithfulness)}</td>
                    <td className="num">{fmtPct(row.refusal_accuracy)}</td>
                    <td className="num">{fmtNum(row.latency_p95_ms, 0)}</td>
                    <td className="num">{fmtNum(row.tokens_per_query, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Correctness Ladder (C1 → C7 by Document)</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 12, fontSize: 13 }}>
          {DOC_ORDER.map((docId) => (
            <span key={docId} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  width: 14,
                  height: 3,
                  background: DOC_COLORS[docId],
                  display: "inline-block",
                }}
              />
              {DOC_LABELS[docId] ?? docId}
            </span>
          ))}
        </div>
        <div style={{ overflowX: "auto" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: "100%", maxWidth: width, height: "auto", display: "block" }}
            role="img"
            aria-label="Correctness from C1 to C7 per document"
          >
            {[0, 0.25, 0.5, 0.75, 1].map((tick) => {
              const y = yFor(tick);
              return (
                <g key={tick}>
                  <line
                    x1={pad.left}
                    y1={y}
                    x2={width - pad.right}
                    y2={y}
                    stroke="#e2e8f0"
                    strokeDasharray="3,3"
                  />
                  <text
                    x={pad.left - 8}
                    y={y + 4}
                    textAnchor="end"
                    fontSize="11"
                    fill="#475569"
                  >
                    {Math.round(tick * 100)}%
                  </text>
                </g>
              );
            })}

            {cfgList.map((cid, idx) => (
              <text
                key={cid}
                x={xFor(idx)}
                y={height - 12}
                textAnchor="middle"
                fontSize="12"
                fontWeight="600"
                fill="#0f172a"
              >
                {cid}
              </text>
            ))}

            {DOC_ORDER.map((docId) => {
              const points = cfgList
                .map((cid, idx) => {
                  const found = data.results.find(
                    (r) => r.config_id === cid && r.doc_id === docId
                  );
                  return found ? { idx, val: found.correctness, cid } : null;
                })
                .filter((p): p is { idx: number; val: number; cid: string } => p !== null);

              if (points.length === 0) return null;
              const d = points
                .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(p.idx)} ${yFor(p.val)}`)
                .join(" ");

              return (
                <g key={docId}>
                  <path d={d} fill="none" stroke={DOC_COLORS[docId]} strokeWidth={2.5} />
                  {points.map((p) => (
                    <circle
                      key={`${docId}-${p.cid}`}
                      cx={xFor(p.idx)}
                      cy={yFor(p.val)}
                      r={4}
                      fill={DOC_COLORS[docId]}
                    >
                      <title>{`${DOC_LABELS[docId]} ${p.cid}: ${(p.val * 100).toFixed(1)}%`}</title>
                    </circle>
                  ))}
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="notice">
        <strong>Note:</strong> With 20 questions per document, differences under 10 percentage points
        are <strong>not conclusive</strong>.
      </div>
    </div>
  );
}
