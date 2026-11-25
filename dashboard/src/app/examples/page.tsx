import { loadResults } from "@/lib/results";

export default function ExamplesPage() {
  const data = loadResults();
  const examples = data.failure_examples ?? [];

  return (
    <div>
      <h1>Failure Examples</h1>
      <p className="subtitle">
        Real failure cases and diagnoses read directly from <code>public/results.json</code>.
      </p>

      {examples.length === 0 ? (
        <div className="card">
          <p style={{ margin: 0, color: "var(--muted)" }}>
            <strong>not run:</strong> No failure examples are recorded in{" "}
            <code>results.json</code> yet. Fill in Section 4 of <code>DECISION_LOG.md</code> and
            re-run the aggregate stage to populate this page.
          </p>
        </div>
      ) : (
        examples.map((ex, idx) => (
          <div className="card" key={`${ex.qid ?? idx}-${ex.config_id ?? idx}`}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
              {ex.config_id && <span className="badge">{ex.config_id}</span>}
              {ex.doc_id && <span className="badge">{ex.doc_id}</span>}
              {ex.qid && <span className="badge">{ex.qid}</span>}
              {ex.stage && <span className="badge">Stage: {ex.stage}</span>}
            </div>
            <p>
              <strong>Question:</strong> {ex.question ?? "—"}
            </p>
            <p>
              <strong>Retrieved snippet:</strong>{" "}
              <span style={{ color: "var(--muted)" }}>{ex.retrieved_snippet ?? "—"}</span>
            </p>
            <p>
              <strong>Model answer:</strong> {ex.answer ?? "—"}
            </p>
            <p>
              <strong>Correct answer:</strong> {ex.gold_answer ?? "—"}
            </p>
            <div className="notice" style={{ marginBottom: 0 }}>
              <strong>Diagnosis:</strong> {ex.diagnosis ?? "—"}
              {ex.fix && (
                <div style={{ marginTop: 6 }}>
                  <strong>Fix:</strong> {ex.fix}
                </div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
