import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Link2, Monitor, ShieldCheck, Smartphone, TriangleAlert, Unlink, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import { me as meApi, oauthStartUrl, qk } from "@/api/endpoints";
import type { Me, Session } from "@/api/types";
import { GitHubIcon, GoogleIcon } from "@/components/BrandIcons";
import {
  Avatar,
  Badge,
  Button,
  Callout,
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
  Row,
  Tooltip,
  useToast,
  type Column,
} from "@/components/ui";
import { useMe } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { useAppConfig } from "@/lib/config";
import { describeAgent } from "@/lib/format";
import { MIN_PASSWORD } from "@/lib/labels";
import { PROVIDER_LABEL } from "@/lib/messages";

export default function Account() {
  usePageMeta([{ label: "Account" }]);
  const { me } = useMe();
  if (!me) return null;
  return (
    <div className="max-w-2xl">
      <PageHeader title="Account" />
      <div className="flex flex-col gap-4">
        <Profile me={me} />
        <SignInMethods me={me} />
        <Password me={me} />
        <Sessions />
        <DangerZone />
      </div>
    </div>
  );
}

function Profile({ me }: { me: Me }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(me.name ?? "");
  const save = useMutation({
    mutationFn: () => meApi.update(name.trim() || null),
    onSuccess: (updated) => {
      qc.setQueryData(qk.me, updated);
      toast.success("Profile saved");
    },
    onError: (e) => toast.error("Couldn't save profile", errorMessage(e)),
  });
  return (
    <Card>
      <CardHeader icon={<UserRound />} title="Profile" />
      <Row label="Email">
        <Avatar src={me.avatar_url} name={me.name ?? me.email} size={22} />
        <span className="truncate text-sm">{me.email}</span>
        {me.email_verified ? <Badge tone="success">Verified</Badge> : <Badge tone="warning">Unverified</Badge>}
      </Row>
      <Row label="Name">
        <form
          className="flex items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Input aria-label="Name" size="sm" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} className="w-56" />
          <Button type="submit" size="sm" loading={save.isPending} disabled={(me.name ?? "") === name.trim()}>
            Save
          </Button>
        </form>
      </Row>
    </Card>
  );
}

function SignInMethods({ me }: { me: Me }) {
  const cfg = useAppConfig();
  const qc = useQueryClient();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const linked = params.get("linked");

  useEffect(() => {
    if (linked) {
      toast.success(`${PROVIDER_LABEL[linked] ?? linked} linked`);
      setParams((p) => {
        p.delete("linked");
        return p;
      }, { replace: true });
    }
  }, [linked, setParams, toast]);

  const unlink = useMutation({
    mutationFn: (id: string) => meApi.unlink(id),
    onSuccess: () => {
      toast.success("Sign-in method removed");
      void qc.invalidateQueries({ queryKey: qk.me });
    },
    onError: (e) => toast.error("Couldn't unlink", errorMessage(e)),
  });

  const methods = me.identities.length + (me.has_password ? 1 : 0);
  const providers = (["github", "google"] as const).filter((p) =>
    p === "github" ? cfg.githubEnabled : cfg.googleEnabled,
  );

  return (
    <Card>
      <CardHeader icon={<Link2 />} title="Sign-in methods" info="You can't remove your only way to sign in." />
      {providers.map((p) => {
        const identity = me.identities.find((i) => i.provider === p);
        const icon = p === "github" ? <GitHubIcon /> : <GoogleIcon />;
        return (
          <Row
            key={p}
            label={
              <span className="flex items-center gap-2">
                {icon}
                {PROVIDER_LABEL[p]}
              </span>
            }
          >
            {identity ? (
              <>
                <span className="truncate text-xs text-fg-muted">{identity.login ?? identity.email}</span>
                <Tooltip content={methods <= 1 ? "Add another sign-in method first." : null}>
                  <span tabIndex={methods <= 1 ? 0 : -1}>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Unlink />}
                      disabled={methods <= 1}
                      loading={unlink.isPending && unlink.variables === identity.id}
                      onClick={() => unlink.mutate(identity.id)}
                    >
                      Unlink
                    </Button>
                  </span>
                </Tooltip>
              </>
            ) : (
              <Button asChild size="sm">
                <a href={oauthStartUrl(p, "link", "/account")}>Link</a>
              </Button>
            )}
          </Row>
        );
      })}
      {me.identities
        .filter((i) => !providers.includes(i.provider as "github" | "google"))
        .map((i) => (
          <Row key={i.id} label={PROVIDER_LABEL[i.provider] ?? i.provider}>
            <span className="text-xs text-fg-muted">{i.login ?? i.email}</span>
          </Row>
        ))}
      <Row
        label={
          <span className="flex items-center gap-2">
            <KeyRound className="size-4 text-fg-subtle" aria-hidden="true" />
            Password
          </span>
        }
      >
        {me.has_password ? <Badge tone="success">Set</Badge> : <Badge>Not set</Badge>}
      </Row>
    </Card>
  );
}

function Password({ me }: { me: Me }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const change = useMutation({
    mutationFn: () => meApi.changePassword({ current_password: me.has_password ? current : null, new_password: next }),
    onSuccess: (ok) => {
      setCurrent("");
      setNext("");
      setSubmitted(false);
      toast.success(me.has_password ? "Password changed" : "Password set", ok.message ?? undefined);
      void qc.invalidateQueries({ queryKey: qk.me });
      void qc.invalidateQueries({ queryKey: qk.sessions });
    },
  });
  const tooShort = next.length < MIN_PASSWORD;
  return (
    <Card>
      <CardHeader icon={<ShieldCheck />} title={me.has_password ? "Change password" : "Set a password"} info="Other sessions are signed out when you change it." />
      <form
        className="grid gap-3 p-3 sm:grid-cols-[1fr_1fr_auto] sm:items-start"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(true);
          if (!tooShort) change.mutate();
        }}
      >
        {me.has_password && (
          <Input
            label="Current"
            type="password"
            autoComplete="current-password"
            required
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
          />
        )}
        <Input
          label="New"
          type="password"
          autoComplete="new-password"
          required
          maxLength={128}
          info={`At least ${MIN_PASSWORD} characters.`}
          value={next}
          onChange={(e) => setNext(e.target.value)}
          error={submitted && tooShort ? `At least ${MIN_PASSWORD} characters.` : null}
          fieldClassName={me.has_password ? undefined : "sm:col-span-2"}
        />
        <Button type="submit" variant="primary" loading={change.isPending} className="sm:mt-5">
          {me.has_password ? "Change" : "Set password"}
        </Button>
        {change.isError && (
          <Callout tone="danger" className="sm:col-span-3">
            {errorMessage(change.error)}
          </Callout>
        )}
      </form>
    </Card>
  );
}

function Sessions() {
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: qk.sessions, queryFn: meApi.sessions });
  const revoke = useMutation({
    mutationFn: (id: string) => meApi.revokeSession(id),
    onSuccess: () => {
      toast.success("Session signed out");
      void qc.invalidateQueries({ queryKey: qk.sessions });
    },
    onError: (e) => toast.error("Couldn't sign out session", errorMessage(e)),
  });
  const columns: Column<Session>[] = [
    {
      key: "device",
      header: "Device",
      cell: (s) => {
        const d = describeAgent(s.user_agent);
        return (
          <span className="flex items-center gap-2">
            {d.mobile ? <Smartphone className="size-4 text-fg-subtle" aria-hidden="true" /> : <Monitor className="size-4 text-fg-subtle" aria-hidden="true" />}
            <span className="font-medium">{d.label}</span>
            {s.current && <Badge tone="success">This device</Badge>}
          </span>
        );
      },
    },
    { key: "ip", header: "IP", className: "hidden sm:table-cell", cell: (s) => <span className="font-mono text-xs text-fg-muted">{s.ip ?? "—"}</span> },
    { key: "seen", header: "Last active", className: "w-28", cell: (s) => <RelativeTime iso={s.last_seen_at} className="text-fg-subtle" /> },
    {
      key: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (s) =>
        s.current ? null : (
          <IconButton size="xs" label="Sign out this session" icon={<Unlink />} loading={revoke.isPending && revoke.variables === s.id} onClick={() => revoke.mutate(s.id)} />
        ),
    },
  ];
  return (
    <Card>
      <CardHeader icon={<Monitor />} title="Sessions" meta={q.data?.length} />
      {q.isError ? (
        <ErrorState compact error={q.error} onRetry={() => void q.refetch()} />
      ) : (
        <DataTable caption="Sessions" columns={columns} rows={q.data} loading={q.isPending} skeletonRows={2} rowKey={(s) => s.id} empty={<EmptyState compact title="No sessions" />} />
      )}
    </Card>
  );
}

function DangerZone() {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const del = useMutation({
    mutationFn: meApi.remove,
    onSuccess: () => {
      qc.clear();
      qc.setQueryData(qk.me, null);
      toast.success("Your account was deleted");
      navigate("/", { replace: true });
    },
    onError: (e) => {
      setOpen(false);
      toast.error("Couldn't delete account", errorMessage(e));
    },
  });
  return (
    <Card className="border-danger/30">
      <CardHeader icon={<TriangleAlert className="text-danger" />} title="Danger zone" />
      <Row label="Delete account" info="Deletes your profile, sessions and workspaces where you're the only member. Transfer admin rights first if others depend on a workspace.">
        <Button size="sm" variant="danger" onClick={() => setOpen(true)}>
          Delete
        </Button>
      </Row>
      <ConfirmDialog
        open={open}
        onOpenChange={setOpen}
        title="Delete your account?"
        description="This can't be undone."
        confirmLabel="Delete account"
        confirmText="delete"
        loading={del.isPending}
        onConfirm={() => del.mutate()}
      />
    </Card>
  );
}
