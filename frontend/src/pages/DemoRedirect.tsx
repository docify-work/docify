import { useQuery } from "@tanstack/react-query";
import { MoonStar } from "lucide-react";
import { Navigate } from "react-router";
import { getDemo } from "@/api/endpoints";
import { EmptyState, ErrorState, PageSpinner } from "@/components/ui";

/** `/demo` → `/w/<demo-slug>` (the API serves the demo through the normal workspace endpoints). */
export default function DemoRedirect() {
  const q = useQuery({ queryKey: ["demo"], queryFn: getDemo, staleTime: 300_000 });
  if (q.isPending) return <PageSpinner />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => void q.refetch()} />;
  if (!q.data.available || !q.data.workspace_slug) {
    return <EmptyState icon={<MoonStar />} title="The demo isn't available right now" />;
  }
  return <Navigate to={`/w/${q.data.workspace_slug}`} replace />;
}
