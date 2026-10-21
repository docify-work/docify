import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { errorMessage, fieldError } from "@/api/client";
import { qk, workspaces } from "@/api/endpoints";
import { Button, Callout, Card, Input } from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";

const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,48}[a-z0-9])$/;

function slugify(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

export default function CreateWorkspace() {
  usePageMeta([{ label: "New workspace" }]);
  const { me } = useMe();
  const first = (me?.workspaces.filter((w) => !w.is_public_demo).length ?? 0) === 0;
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const effectiveSlug = slugEdited ? slug : slugify(name);
  const slugInvalid = slugEdited && !SLUG.test(slug);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const create = useMutation({
    // Untouched slug → let the API derive a unique one from the name.
    mutationFn: () => workspaces.create({ name: name.trim(), slug: slugEdited ? slug : null }),
    onSuccess: async (ws) => {
      await qc.invalidateQueries({ queryKey: qk.me });
      navigate(`/w/${ws.slug}/repos`, { replace: true });
    },
  });

  return (
    <div className="mx-auto max-w-md pt-[6vh]">
      <h1 className="text-xl font-semibold tracking-tight">{first ? "Create your first workspace" : "New workspace"}</h1>
      <p className="mt-1 text-sm text-fg-muted">A workspace holds repositories, docs and members.</p>
      <Card className="mt-5 p-4">
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <Input
            label="Name"
            required
            autoFocus
            maxLength={120}
            placeholder="Acme Engineering"
            value={name}
            onChange={(e) => setName(e.target.value)}
            error={fieldError(create.error, "name")}
          />
          <Input
            label="URL"
            info="Used in links: /w/<slug>. Lowercase letters, numbers and dashes."
            maxLength={50}
            value={effectiveSlug}
            placeholder="acme"
            onChange={(e) => {
              setSlugEdited(true);
              setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"));
            }}
            error={(slugInvalid && slug ? "3–50 lowercase letters, digits or dashes." : null) ?? fieldError(create.error, "slug")}
          />
          {create.isError && !fieldError(create.error, "name") && !fieldError(create.error, "slug") && (
            <Callout tone="danger">{errorMessage(create.error)}</Callout>
          )}
          <Button type="submit" variant="primary" loading={create.isPending} disabled={name.trim().length < 2 || slugInvalid}>
            Create workspace
          </Button>
        </form>
      </Card>
    </div>
  );
}
