import { useApi } from "../lib/useApi";
import { Org } from "../types";
export default function SyntheticBanner() {
  const { data } = useApi<Org>("/api/org");
  return data?.is_synthetic ? <div className="mb-4 rounded-lg bg-amber-50 p-2 text-center text-xs text-amber-800">This organization contains SYNTHETIC demo data generated for illustration. It is not real customer data.</div> : null;
}
