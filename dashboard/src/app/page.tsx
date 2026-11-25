import { OverviewClient } from "@/components/OverviewClient";
import { loadResults } from "@/lib/results";

export default function OverviewPage() {
  const data = loadResults();
  return <OverviewClient data={data} />;
}
