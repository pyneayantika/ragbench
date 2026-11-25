"use client";

import { useState } from "react";
import { BenchmarkResults, DOC_LABELS, StageKey } from "@/lib/types";

const DOC_ORDER = ["annual_report", "fund_doc", "ghg_scope3"];
const STAGES: { key: StageKey; label: string; color: string }[] = [
  { key: "ingestion", label: "Ingestion", color: "#94a3b8" },
  { key: "indexing", label: "Indexing", color: "#64748b" },
  { key: "retrieval", label: "Retrieval", color: "#2563eb" },
  { key: "generation", label: "Generation", color: "#0f172a" },
];

export function FailuresClient({ data }: { data: BenchmarkResults }) {
  const [selectedDoc, setSelectedDoc] = useState<string>("annual_report");
  const cfgList = data.configs.map((c) => c.config_id);

  const rows = cfgList.map((cid) => {
    const found = data.results.find((r) => r.config_id === cid && r.doc_id === selectedDoc);
    return {
      config_id: cid,
      failures: found ? found.failures_by_stage : null,
      total: found
        ? STAGES.reduce((acc, s) => acc + (found.failures_by_stage[s.key] ?? 0), 0)
        : 0,
    };
  });

  const maxTotal = Math.max(1, ...rows.map((r) => r.total));
  const width = 760;
  const height = 280;
  const pad = { top: 20, right: 20, bottom: 38, left: 44 };
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;
  const slotW = innerW / Math.max(1, rows.length);
  const barW = Math.min(48, slotW * 0.55);

  return (
    <div>
      <h1>Where It Breaks</h1>
      <p className="subtitle">
        Stage-by-stage attribution of wrong or missed answers per configuration, read from{" "}
        <code>public/results.json</code>.
      </p>

      <div className="tabs" role="tablist" aria-label="Document filter">
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
          Failures by Stage — {DOC_LABELS[selectedDoc] ?? selectedDoc}
        </h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, marginBottom: 14, fontSize: 13 }}>
          {STAGES.map((s) => (
            <span key={s.key} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  width: 12,
                  height: 12,
                  background: s.color,
                  display: "inline-block",
                  borderRadius: 2,
                }}
              />
              {s.label}
            </span>
          ))}
        </div>

        <div style={{ overflowX: "auto" }}>
          <svg
            viewBox={`0 0 ${width} ${height}`}
            style={{ width: "100%", maxWidth: width, height: "auto", display: "block" }}
            role="img"
            aria-label="Stacked bar chart of failures by stage"
          >
            {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
              const val = Math.round(frac * maxTotal);
              const y = pad.top + innerH - (val / maxTotal) * innerH;
              return (
                <g key={frac}>
                  <line
                    x1={pad.left}
                    y1={y}
                    x2={width - pad.right}
                    y2={y}
                    stroke="#e2e8f0"
                    strokeDasharray="3,3"
                  />
                  <text x={pad.left - 8} y={y + 4} textAnchor="end" fontSize="11" fill="#475569">
                    {val}
                  </text>
                </g>
              );
            })}

            {rows.map((row, idx) => {
              const cx = pad.left + idx * slotW + slotW / 2;
              const x = cx - barW / 2;
              let currentY = pad.top + innerH;

              return (
                <g key={row.config_id}>
                  {row.failures &&
                    STAGES.map((s) => {
                      const count = row.failures?.[s.key] ?? 0;
                      if (count <= 0) return null;
                      const h = (count / maxTotal) * innerH;
                      const y = currentY - h;
                      currentY = y;
                      return (
                        <rect key={s.key} x={x} y={y} width={barW} height={h} fill={s.color}>
                          <title>{`${row.config_id} ${s.label}: ${count}`}</title>
                        </rect>
                      );
                    })}
                  <text
                    x={cx}
                    y={pad.top + innerH - (row.total / maxTotal) * innerH - 6}
                    textAnchor="middle"
                    fontSize="11"
                    fill="#475569"
                  >
                    {row.failures ? row.total : "not run"}
                  </text>
                  <text
                    x={cx}
                    y={height - 12}
                    textAnchor="middle"
                    fontSize="12"
                    fontWeight="600"
                    fill="#0f172a"
                  >
                    {row.config_id}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Stage Breakdown Table</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Config</th>
                <th className="num">Ingestion</th>
                <th className="num">Indexing</th>
                <th className="num">Retrieval</th>
                <th className="num">Generation</th>
                <th className="num">Total Failures</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.config_id}>
                  <td>
                    <strong>{r.config_id}</strong>
                  </td>
                  {STAGES.map((s) => (
                    <td key={s.key} className="num">
                      {r.failures ? r.failures[s.key] : "not run"}
                    </td>
                  ))}
                  <td className="num">
                    <strong>{r.failures ? r.total : "not run"}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
