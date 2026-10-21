import { useMutation, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Settings2, ShieldCheck, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { errorMessage } from "@/api/client";
import { qk, workspaces } from "@/api/endpoints";
import type { Workspace, WorkspacePatch } from "@/api/types";
import { Button, Card, CardHeader, ConfirmDialog, Input, PageHeader, Row, Switch, useToast } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";

export default function Settings() {
  const { ws, slug } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Settings" }]);
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState(ws.name);
  const [deleteOpen, setDeleteOpen] = useState(false);

  const patch = useMutation({
    mutationFn: (body: WorkspacePatch) => workspaces.update(slug, body),
    onMutate: async (body) => {
      // Optimistic toggle so switches feel instant.
      await qc.cancelQueries({ queryKey: qk.workspace(slug) });
      const prev = qc.getQueryData<Workspace>(qk.workspace(slug));
      if (prev && body.settings) {
        qc.setQueryData<Workspace>(qk.workspace(slug), {
          ...prev,
          settings: {
            auto_publish: body.settings.auto_publish ?? prev.settings.auto_publish,
            chat_enabled: body.settings.chat_enabled ?? prev.settings.chat_enabled,
          },
        });
      }
      return { prev };
    },
    onSuccess: (updated, body) => {
      qc.setQueryData(qk.workspace(slug), updated);
      if (body.name) {
        toast.success("Workspace renamed");
        void qc.invalidateQueries({ queryKey: qk.me });
      }
    },
    onError: (e, _b, ctx) => {
      if (ctx?.prev) qc.setQueryData(qk.workspace(slug), ctx.prev);
      toast.error("Couldn't save", errorMessage(e));
    },
  });

  const remove = useMutation({
    mutationFn: () => workspaces.remove(slug),
    onSuccess: async () => {
      toast.success("Workspace deleted");
      await qc.invalidateQueries({ queryKey: qk.me });
      qc.removeQueries({ queryKey: ["ws", slug] });
      navigate("/app", { replace: true });
    },
    onError: (e) => toast.error("Couldn't delete workspace", errorMessage(e)),
  });

  const autoPublish = ws.settings.auto_publish ?? true;
  const chatEnabled = ws.settings.chat_enabled ?? true;

  return (
    <div className="max-w-2xl">
      <PageHeader title="Settings" />
      <div className="flex flex-col gap-4">
        <Card>
          <CardHeader icon={<Settings2 />} title="General" />
          <Row label="Name">
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (name.trim() && name.trim() !== ws.name) patch.mutate({ name: name.trim() });
              }}
            >
              <Input aria-label="Workspace name" size="sm" value={name} onChange={(e) => setName(e.target.value)} maxLength={120} className="w-56" />
              <Button type="submit" size="sm" disabled={!name.trim() || name.trim() === ws.name} loading={patch.isPending && !!patch.variables?.name}>
                Save
              </Button>
            </form>
          </Row>
          <Row label="URL" info="The workspace URL can't be changed.">
            <code className="text-xs text-fg-muted">/w/{ws.slug}</code>
          </Row>
        </Card>

        <Card>
          <CardHeader icon={<ShieldCheck />} title="Publishing" />
          <Row label="Require approval" info="New doc versions and changelog entries wait in Review until an admin approves them. Off = publish automatically.">
            <Switch
              aria-label="Require approval"
              checked={!autoPublish}
              onCheckedChange={(v) => patch.mutate({ settings: { auto_publish: !v } })}
            />
          </Row>
        </Card>

        <Card>
          <CardHeader icon={<MessageSquare />} title="Chat" />
          <Row label="Enable chat" info="Lets members (and demo visitors, for the demo workspace) ask questions about the code.">
            <Switch aria-label="Enable chat" checked={chatEnabled} onCheckedChange={(v) => patch.mutate({ settings: { chat_enabled: v } })} />
          </Row>
        </Card>

        <Card className="border-danger/30">
          <CardHeader icon={<TriangleAlert className="text-danger" />} title="Danger zone" />
          <Row label="Delete workspace" info="Removes all repositories, docs, chats and members. This can't be undone.">
            <Button size="sm" variant="danger" onClick={() => setDeleteOpen(true)}>
              Delete
            </Button>
          </Row>
        </Card>
      </div>

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title={`Delete ${ws.name}?`}
        description="All data in this workspace is deleted."
        confirmLabel="Delete workspace"
        confirmText={ws.slug}
        loading={remove.isPending}
        onConfirm={() => remove.mutate()}
      />
    </div>
  );
}
