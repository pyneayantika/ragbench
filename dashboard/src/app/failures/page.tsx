import { FailuresClient } from "@/components/FailuresClient";
import { loadResults } from "@/lib/results";

export default function FailuresPage() {
  const data = loadResults();
  return <FailuresClient data={data} />;
}
