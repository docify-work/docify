import { Navigate } from "react-router";
import { useMe } from "@/hooks/useMe";
import { lastWorkspace } from "@/hooks/useWorkspace";

/** `/app`: last-used workspace → first own workspace → onboarding (create first workspace). */
export default function Home() {
  const { me } = useMe();
  if (!me) return null;
  const last = lastWorkspace();
  const own = me.workspaces.filter((w) => !w.is_public_demo);
  const target = me.workspaces.find((w) => w.slug === last) ?? own[0] ?? me.workspaces[0];
  return <Navigate to={target ? `/w/${target.slug}` : "/new"} replace />;
}
