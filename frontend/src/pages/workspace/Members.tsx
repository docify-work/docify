import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LogOut, Mail, Send, UserMinus, Users, X } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { errorMessage, fieldError } from "@/api/client";
import { qk, workspaces } from "@/api/endpoints";
import type { Invite, Member, Role } from "@/api/types";
import {
  Avatar,
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  DataTable,
  EmptyState,
  ErrorState,
  IconButton,
  Input,
  PageHeader,
  RelativeTime,
  Select,
  useToast,
  type Column,
} from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useWorkspace } from "@/hooks/useWorkspace";

const ROLE_OPTIONS = [
  { value: "member", label: "Member" },
  { value: "admin", label: "Admin" },
];

export default function Members() {
  const { ws, slug, isAdmin } = useWorkspace();
  usePageMeta([{ label: ws.name, to: `/w/${slug}` }, { label: "Members" }]);
  const { me } = useMe();
  const qc = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const membersQ = useQuery({ queryKey: qk.members(slug), queryFn: () => workspaces.members(slug) });
  const [removing, setRemoving] = useState<Member | null>(null);
  const [leaveOpen, setLeaveOpen] = useState(false);

  const setRole = useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: Role }) => workspaces.setRole(slug, userId, role),
    onSuccess: () => {
      toast.success("Role updated");
      void qc.invalidateQueries({ queryKey: qk.members(slug) });
    },
    onError: (e) => toast.error("Couldn't change role", errorMessage(e)),
  });
  const removeMember = useMutation({
    mutationFn: (userId: string) => workspaces.removeMember(slug, userId),
    onSuccess: () => {
      setRemoving(null);
      toast.success("Member removed");
      void qc.invalidateQueries({ queryKey: qk.members(slug) });
      void qc.invalidateQueries({ queryKey: qk.workspace(slug) });
    },
    onError: (e) => toast.error("Couldn't remove member", errorMessage(e)),
  });
  const leave = useMutation({
    mutationFn: () => workspaces.leave(slug),
    onSuccess: async () => {
      toast.success(`You left ${ws.name}`);
      await qc.invalidateQueries({ queryKey: qk.me });
      navigate("/app", { replace: true });
    },
    onError: (e) => {
      setLeaveOpen(false);
      toast.error("Couldn't leave workspace", errorMessage(e));
    },
  });

  const columns: Column<Member>[] = [
    {
      key: "member",
      header: "Member",
      cell: (m) => (
        <span className="flex min-w-0 items-center gap-2.5">
          <Avatar src={m.avatar_url} name={m.name ?? m.email} size={24} />
          <span className="min-w-0">
            <span className="block truncate font-medium">
              {m.name ?? m.email.split("@")[0]}
              {m.user_id === me?.id && <span className="ml-1.5 text-xs font-normal text-fg-subtle">(you)</span>}
            </span>
            <span className="block truncate text-xs text-fg-subtle">{m.email}</span>
          </span>
        </span>
      ),
    },
    {
      key: "role",
      header: "Role",
      className: "w-32",
      cell: (m) =>
        isAdmin ? (
          <Select
            size="sm"
            aria-label={`Role for ${m.email}`}
            options={ROLE_OPTIONS}
            value={m.role}
            disabled={setRole.isPending}
            onChange={(e) => setRole.mutate({ userId: m.user_id, role: e.target.value as Role })}
          />
        ) : (
          <Badge tone={m.role === "admin" ? "accent" : "neutral"} className="capitalize">
            {m.role}
          </Badge>
        ),
    },
    { key: "joined", header: "Joined", className: "hidden sm:table-cell w-28", cell: (m) => <RelativeTime iso={m.joined_at} className="text-fg-subtle" /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (m) =>
        isAdmin && m.user_id !== me?.id ? (
          <IconButton size="xs" label="Remove member" icon={<UserMinus />} onClick={() => setRemoving(m)} />
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Members"
        meta={membersQ.data && <span className="tabular">{membersQ.data.length}</span>}
        actions={
          <Button size="sm" variant="ghost" icon={<LogOut />} onClick={() => setLeaveOpen(true)}>
            Leave
          </Button>
        }
      />
      <div className="flex flex-col gap-4">
        {isAdmin && <Invites />}
        <Card>
          {membersQ.isError ? (
            <ErrorState error={membersQ.error} onRetry={() => void membersQ.refetch()} />
          ) : (
            <DataTable
              caption="Members"
              columns={columns}
              rows={membersQ.data}
              loading={membersQ.isPending}
              rowKey={(m) => m.user_id}
              empty={<EmptyState icon={<Users />} title="No members" />}
            />
          )}
        </Card>
      </div>

      <ConfirmDialog
        open={!!removing}
        onOpenChange={(o) => !o && setRemoving(null)}
        title={`Remove ${removing?.name ?? removing?.email ?? "member"}?`}
        description="They lose access to this workspace immediately."
        confirmLabel="Remove"
        loading={removeMember.isPending}
        onConfirm={() => removing && removeMember.mutate(removing.user_id)}
      />
      <ConfirmDialog
        open={leaveOpen}
        onOpenChange={setLeaveOpen}
        title={`Leave ${ws.name}?`}
        description="You'll need a new invite to come back."
        confirmLabel="Leave"
        loading={leave.isPending}
        onConfirm={() => leave.mutate()}
      />
    </>
  );
}

function Invites() {
  const { slug } = useWorkspace();
  const qc = useQueryClient();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRoleValue] = useState<Role>("member");
  const q = useQuery({ queryKey: qk.invites(slug), queryFn: () => workspaces.invites(slug) });

  const invite = useMutation({
    mutationFn: () => workspaces.invite(slug, { email: email.trim(), role }),
    onSuccess: (inv) => {
      setEmail("");
      toast.success("Invite sent", inv.email);
      void qc.invalidateQueries({ queryKey: qk.invites(slug) });
    },
  });
  const revoke = useMutation({
    mutationFn: (id: string) => workspaces.revokeInvite(slug, id),
    onSuccess: () => {
      toast.success("Invite revoked");
      void qc.invalidateQueries({ queryKey: qk.invites(slug) });
    },
    onError: (e) => toast.error("Couldn't revoke invite", errorMessage(e)),
  });

  const columns: Column<Invite>[] = [
    { key: "email", header: "Email", cell: (i) => <span className="flex items-center gap-2"><Mail className="size-3.5 text-fg-subtle" aria-hidden="true" />{i.email}</span> },
    { key: "role", header: "Role", className: "w-24", cell: (i) => <Badge className="capitalize">{i.role}</Badge> },
    { key: "expires", header: "Expires", className: "hidden sm:table-cell w-28", cell: (i) => <RelativeTime iso={i.expires_at} className="text-fg-subtle" /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (i) => (
        <IconButton size="xs" label="Revoke invite" icon={<X />} loading={revoke.isPending && revoke.variables === i.id} onClick={() => revoke.mutate(i.id)} />
      ),
    },
  ];

  return (
    <Card>
      <CardHeader icon={<Send />} title="Invites" meta={q.data?.length || undefined} info="Invitees get an email link. They must sign in with that (verified) address to join." />
      <form
        className="flex flex-wrap items-start gap-2 border-b border-border p-3"
        onSubmit={(e) => {
          e.preventDefault();
          invite.mutate();
        }}
      >
        <Input
          aria-label="Email to invite"
          type="email"
          required
          placeholder="name@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          fieldClassName="flex-1 min-w-48"
          className="min-w-48"
          error={invite.isError ? (fieldError(invite.error, "email") ?? errorMessage(invite.error)) : null}
        />
        <Select aria-label="Role" options={ROLE_OPTIONS} value={role} onChange={(e) => setRoleValue(e.target.value as Role)} className="w-28" />
        <Button type="submit" variant="primary" loading={invite.isPending} disabled={!email.trim()}>
          Invite
        </Button>
      </form>
      {q.isError ? (
        <ErrorState compact error={q.error} onRetry={() => void q.refetch()} />
      ) : (q.data?.length ?? 0) > 0 || q.isPending ? (
        <DataTable caption="Pending invites" columns={columns} rows={q.data} loading={q.isPending} skeletonRows={2} rowKey={(i) => i.id} />
      ) : null}
    </Card>
  );
}
