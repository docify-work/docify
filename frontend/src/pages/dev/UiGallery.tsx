import { Bell, FileText, FolderGit2, Plus, RefreshCw, Settings, Trash2, Users } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Markdown } from "@/components/Markdown";
import { CodeSnippet, Highlighted } from "@/components/Snippets";
import {
  Avatar,
  Badge,
  Breadcrumbs,
  Button,
  Callout,
  Card,
  CardHeader,
  Checkbox,
  ConfirmDialog,
  CopyButton,
  DataTable,
  Dialog,
  Drawer,
  DropdownMenu,
  EmptyState,
  ErrorState,
  IconButton,
  InfoTip,
  Input,
  KeyValues,
  Kbd,
  List,
  ListItem,
  MenuItem,
  MenuLabel,
  MenuSeparator,
  PageHeader,
  Popover,
  RelativeTime,
  Row,
  Select,
  Skeleton,
  SkeletonRows,
  SkeletonText,
  Spinner,
  Stat,
  StatusPill,
  Switch,
  Tabs,
  Textarea,
  Tooltip,
  useToast,
  type Column,
} from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";

const STATUSES = ["pending", "indexing", "ready", "error", "empty", "too_large", "suspended", "queued", "running", "succeeded", "failed", "dead", "blocked_budget", "pending_review"];
const ago = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

interface Demo {
  id: string;
  name: string;
  status: string;
  at: string;
}
const ROWS: Demo[] = [
  { id: "1", name: "acme/api", status: "ready", at: ago(3) },
  { id: "2", name: "acme/web", status: "indexing", at: ago(42) },
  { id: "3", name: "acme/infra", status: "error", at: ago(60 * 26) },
];

const MD = `## Setup\n\nRun \`make up\` then open the app. See [config.py](https://github.com/acme/api/blob/abc/config.py#L1-L9).\n\n| Var | Default |\n| --- | --- |\n| \`ENV\` | local |\n\n\`\`\`bash\nnpm ci && npm run dev\n\`\`\`\n\n<script>alert(1)</script> ![img](https://x/y.png) [bad](javascript:alert(1))`;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader title={title} />
      <div className="flex flex-wrap items-center gap-3 p-4">{children}</div>
    </Card>
  );
}

/** Dev-only visual review of every UI kit component (`/dev/ui`). */
export default function UiGallery() {
  usePageMeta([{ label: "UI kit" }]);
  const toast = useToast();
  const [sw, setSw] = useState(true);
  const [cb, setCb] = useState(false);
  const [tab, setTab] = useState<"a" | "b" | "c">("a");
  const [dialog, setDialog] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [drawer, setDrawer] = useState(false);
  const [loading, setLoading] = useState(false);
  const cols: Column<Demo>[] = [
    { key: "name", header: "Repository", cell: (r) => <span className="font-medium">{r.name}</span> },
    { key: "status", header: "Status", cell: (r) => <StatusPill status={r.status} /> },
    { key: "at", header: "Updated", align: "right", info: "Tooltip on a header", cell: (r) => <RelativeTime iso={r.at} /> },
  ];

  return (
    <div className="flex flex-col gap-4">
      <PageHeader title="UI kit" info="Every shared component, for visual review in light and dark." meta={<Badge tone="accent">dev</Badge>} actions={<Button size="sm" variant="primary" icon={<Plus />}>Primary action</Button>} />
      <Breadcrumbs items={[{ label: "Acme", to: "/" }, { label: "Repositories", to: "/" }, { label: "acme/api" }]} />

      <Section title="Buttons">
        <Button variant="primary">Primary</Button>
        <Button>Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="subtle">Subtle</Button>
        <Button variant="danger" icon={<Trash2 />}>Danger</Button>
        <Button size="sm" icon={<RefreshCw />}>Small</Button>
        <Button size="xs">Extra small</Button>
        <Button loading={loading} onClick={() => { setLoading(true); setTimeout(() => setLoading(false), 1200); }}>Click to load</Button>
        <Button disabled>Disabled</Button>
        <IconButton label="Settings" icon={<Settings />} />
        <IconButton label="Notifications" variant="secondary" icon={<Bell />} />
        <CopyButton value="copied text" />
        <Kbd>Ctrl</Kbd>
        <Kbd>K</Kbd>
      </Section>

      <Section title="Badges & status">
        <Badge>Neutral</Badge>
        <Badge tone="accent">Accent</Badge>
        <Badge tone="success">Success</Badge>
        <Badge tone="warning">Warning</Badge>
        <Badge tone="danger">Danger</Badge>
        <Badge tone="info">Info</Badge>
        {STATUSES.map((s) => <StatusPill key={s} status={s} />)}
      </Section>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Form controls" info="Labels with ⓘ tooltips instead of paragraphs." />
          <div className="flex flex-col gap-3 p-4">
            <Input label="Email" placeholder="name@company.com" info="We never share it." />
            <Input label="With error" defaultValue="nope" error="This value is invalid." />
            <Select label="Role" options={[{ value: "member", label: "Member" }, { value: "admin", label: "Admin" }]} />
            <Textarea label="Notes" placeholder="Type…" />
            <Checkbox checked={cb} onCheckedChange={setCb} label="Checkbox" info="Helper text" />
          </div>
        </Card>
        <Card>
          <CardHeader title="Rows, switches, tabs" />
          <Row label="Require approval" info="Settings-style row">
            <Switch aria-label="Require approval" checked={sw} onCheckedChange={setSw} />
          </Row>
          <Row label="Tabs (pills)">
            <Tabs value={tab} onValueChange={setTab} items={[{ value: "a", label: "Code" }, { value: "b", label: "Docs", count: 12 }, { value: "c", label: "All" }]} />
          </Row>
          <Row label="Tabs (underline)">
            <Tabs variant="underline" value={tab} onValueChange={setTab} items={[{ value: "a", label: "One" }, { value: "b", label: "Two" }, { value: "c", label: "Three" }]} />
          </Row>
          <Row label="Avatars">
            <Avatar name="Ganesh K" />
            <Avatar name="supriya@example.com" size={28} />
          </Row>
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Repositories" value={12} icon={<FolderGit2 />} />
        <Stat label="Documents" value={36} icon={<FileText />} info="Published docs" />
        <Stat label="Members" value={4} icon={<Users />} />
        <Stat label="Loading" value={<Skeleton className="mt-1 h-4 w-10" />} />
      </div>

      <KeyValues items={[{ label: "Branch", value: "main" }, { label: "Commit", value: "abc1234" }, { label: "Synced", value: <RelativeTime iso={ago(5)} /> }, { label: "Added", value: <RelativeTime iso={ago(60 * 24 * 9)} /> }]} />

      <Section title="Overlays & feedback">
        <Tooltip content="A tooltip"><Button size="sm">Tooltip</Button></Tooltip>
        <span className="flex items-center gap-1 text-sm">InfoTip <InfoTip>Short helper text lives here.</InfoTip></span>
        <Popover trigger={<Button size="sm">Popover</Button>}><p className="text-xs">Popover content</p></Popover>
        <DropdownMenu trigger={<Button size="sm">Dropdown</Button>}>
          <MenuLabel>Actions</MenuLabel>
          <MenuItem icon={<RefreshCw />}>Sync</MenuItem>
          <MenuSeparator />
          <MenuItem icon={<Trash2 />} danger>Remove</MenuItem>
        </DropdownMenu>
        <Button size="sm" onClick={() => setDialog(true)}>Dialog</Button>
        <Button size="sm" onClick={() => setConfirm(true)}>Confirm</Button>
        <Button size="sm" onClick={() => setDrawer(true)}>Drawer</Button>
        <Button size="sm" onClick={() => toast.success("Saved", "Everything is fine.")}>Toast ✓</Button>
        <Button size="sm" onClick={() => toast.error("Failed", "Something broke.")}>Toast ✗</Button>
        <Spinner />
      </Section>

      <div className="flex flex-col gap-2">
        <Callout tone="info">Info callout</Callout>
        <Callout tone="success">Success callout</Callout>
        <Callout tone="warning" onDismiss={() => undefined}>Warning callout with dismiss</Callout>
        <Callout tone="danger">Danger callout</Callout>
      </div>

      <Card>
        <CardHeader title="DataTable" meta={ROWS.length} />
        <DataTable columns={cols} rows={ROWS} rowKey={(r) => r.id} onRowClick={(r) => toast.toast({ title: r.name })} />
      </Card>
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="List" />
          <List>
            {ROWS.map((r, i) => <ListItem key={r.id} index={i} to="/dev/ui" icon={<FolderGit2 />} title={r.name} subtitle="Updated recently" meta={<StatusPill status={r.status} />} />)}
          </List>
        </Card>
        <Card>
          <CardHeader title="Loading & empty" />
          <SkeletonRows rows={2} />
          <div className="p-3"><SkeletonText lines={2} /></div>
          <EmptyState compact icon={<FileText />} title="No docs yet" info="Helper in a tooltip" action={<Button size="sm">Action</Button>} />
          <ErrorState compact error={new Error("Example failure")} onRetry={() => undefined} />
        </Card>
      </div>

      <Card className="p-5">
        <Markdown>{MD}</Markdown>
        <p className="mt-3 text-xs"><Highlighted text="search <b>hit</b> highlight" /></p>
      </Card>
      <Card className="overflow-hidden"><CodeSnippet code={"def main():\n    print('hi')\n…"} startLine={10} /></Card>

      <Dialog open={dialog} onOpenChange={setDialog} title="Dialog title" description="One short line." footer={<Button size="sm" variant="primary" onClick={() => setDialog(false)}>Done</Button>}>
        <Input label="Field" />
      </Dialog>
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Delete acme?" description="This can't be undone." confirmText="acme" confirmLabel="Delete" onConfirm={() => setConfirm(false)} />
      <Drawer open={drawer} onOpenChange={setDrawer} title="Drawer">
        <div className="p-3 text-sm">Drawer content</div>
      </Drawer>
    </div>
  );
}
