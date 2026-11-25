import { loadResults } from "@/lib/results";

export default function MethodPage() {
  const data = loadResults();
  const agreement = data.judge_agreement;
  const agreementText = agreement
    ? `${agreement.agreed} / ${agreement.n} (${((agreement.agreed / agreement.n) * 100).toFixed(1)}%)`
    : "not run";

  return (
    <div>
      <h1>Method &amp; Integrity</h1>
      <p className="subtitle">
        Evaluation design, golden set structure, and verification metadata read from{" "}
        <code>public/results.json</code>.
      </p>

      <div className="grid-2" style={{ marginBottom: 20 }}>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="kpi-label">Judge–Human Agreement</div>
          <div className="kpi-value">{agreementText}</div>
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="kpi-label">Fuzzy-Match Threshold</div>
          <div className="kpi-value">{data.fuzzy_threshold}</div>
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="kpi-label">Configs Evaluated</div>
          <div className="kpi-value">{data.configs.length}</div>
        </div>
        <div className="card" style={{ marginBottom: 0 }}>
          <div className="kpi-label">Generated At (UTC)</div>
          <div className="kpi-value" style={{ fontSize: 16 }}>
            {data.generated_at}
          </div>
        </div>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Golden Set Mix</h2>
        <p>
          60 hand-written questions across 3 public PDFs (20 questions per document: Infosys Annual
          Report, HDFC Mutual Fund Factsheet, and GHG Protocol Scope 3 Guidance). Questions cover
          factual lookups, table extraction, multi-part synthesis, paraphrased queries, and 2
          unanswerable questions per document to test refusal accuracy.
        </p>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Metrics &amp; Attribution</h2>
        <ul>
          <li>
            <strong>Hit@5 &amp; MRR:</strong> Whether the supporting text appears in the top 5
            retrieved chunks (using <code>rapidfuzz.fuzz.partial_ratio</code> at threshold{" "}
            <code>{data.fuzzy_threshold}</code>).
          </li>
          <li>
            <strong>Correctness &amp; Faithfulness:</strong> Graded by a separate-family LLM judge (
            <code>0</code>, <code>0.5</code>, or <code>1</code>) with <code>temperature=0</code>,
            calibrated against {agreement ? `${agreement.n}` : "20"} blind human scores.
          </li>
          <li>
            <strong>Refusal Accuracy:</strong> Whether unanswerable questions receive the exact
            refusal response.
          </li>
          <li>
            <strong>Stage Attribution:</strong> Every wrong answer is traced to the first stage
            that broke (<code>ingestion → indexing → retrieval → generation</code>).
          </li>
        </ul>
      </div>

      <div className="card">
        <h2 style={{ marginTop: 0 }}>Configuration Ladder</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Config</th>
                <th>Stage Changed</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {data.configs.map((c) => (
                <tr key={c.config_id}>
                  <td>
                    <strong>{c.config_id}</strong>
                  </td>
                  <td>{c.stage_changed ?? "baseline"}</td>
                  <td style={{ whiteSpace: "normal" }}>{c.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="notice">
        <strong>Statistical Caveat:</strong> With 20 questions per document,{" "}
        <strong>differences under 10 points are not conclusive</strong>.
      </div>

      <div className="footer-note">
        Source repository:{" "}
        <a href="https://github.com" target="_blank" rel="noreferrer">
          RAGBench on GitHub
        </a>{" "}
        (update this URL with your public repo link before sharing).
      </div>
    </div>
  );
}
