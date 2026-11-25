export type StageKey = "ingestion" | "indexing" | "retrieval" | "generation";

export interface ConfigInfo {
  config_id: string;
  stage_changed: string | null;
  description: string;
}

export interface DocResult {
  config_id: string;
  doc_id: string;
  hit_at_5: number;
  mrr: number;
  correctness: number;
  faithfulness: number;
  refusal_accuracy: number;
  over_refusals: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  tokens_per_query: number;
  failures_by_stage: Record<StageKey, number>;
}

export interface FailureExample {
  qid?: string;
  config_id?: string;
  doc_id?: string;
  question?: string;
  retrieved_snippet?: string;
  answer?: string;
  gold_answer?: string;
  stage?: string;
  diagnosis?: string;
  fix?: string;
}

export interface BenchmarkResults {
  generated_at: string;
  judge_agreement: { n: number; agreed: number } | null;
  fuzzy_threshold: number;
  configs: ConfigInfo[];
  results: DocResult[];
  winners: Record<string, string>;
  failure_examples: FailureExample[];
}

export const DOC_LABELS: Record<string, string> = {
  annual_report: "Annual Report (Infosys)",
  fund_doc: "Fund Factsheet (HDFC)",
  ghg_scope3: "GHG Scope 3 Guidance",
};
