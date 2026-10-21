import { Compass } from "lucide-react";
import { Link } from "react-router";
import { Button, EmptyState } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function NotFound({ inline = false }: { inline?: boolean }) {
  usePageMeta([{ label: "Not found" }]);
  return (
    <div className={inline ? undefined : "flex flex-1 items-center justify-center px-4 py-20"}>
      <EmptyState
        icon={<Compass />}
        title={
          <span>
            <span className="tabular mr-2 text-fg-subtle">404</span>Page not found
          </span>
        }
        action={
          <Button asChild size="sm">
            <Link to="/">Go home</Link>
          </Button>
        }
      />
    </div>
  );
}
