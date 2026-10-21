import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import { auth, qk } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { Button, Callout, EmptyState, Input, TextLink } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";
import { MIN_PASSWORD } from "@/lib/labels";

export default function ResetPassword() {
  usePageMeta([{ label: "Choose a new password" }]);
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const qc = useQueryClient();
  const reset = useMutation({
    mutationFn: () => auth.resetPassword(token, password),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me }),
  });
  const tooShort = password.length < MIN_PASSWORD;
  const mismatch = confirm !== password;

  if (!token) {
    return (
      <AuthCard title="Choose a new password">
        <Callout tone="danger">This link is missing its token.</Callout>
        <div className="mt-3 text-sm">
          <TextLink to="/forgot-password">Request a new link</TextLink>
        </div>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Choose a new password">
      {reset.isSuccess ? (
        <EmptyState
          compact
          icon={<CheckCircle2 className="text-success" />}
          title="Password updated"
          info="All other sessions were signed out."
          action={
            <Button asChild size="sm" variant="primary">
              <Link to="/app">Continue</Link>
            </Button>
          }
        />
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
            if (!tooShort && !mismatch) reset.mutate();
          }}
        >
          <Input
            label="New password"
            type="password"
            autoComplete="new-password"
            required
            autoFocus
            maxLength={128}
            info={`At least ${MIN_PASSWORD} characters.`}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={submitted && tooShort ? `At least ${MIN_PASSWORD} characters.` : null}
          />
          <Input
            label="Confirm password"
            type="password"
            autoComplete="new-password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            error={submitted && mismatch ? "Passwords don't match." : null}
          />
          {reset.isError && (
            <Callout tone="danger" action={<TextLink to="/forgot-password">New link</TextLink>}>
              {errorMessage(reset.error)}
            </Callout>
          )}
          <Button type="submit" variant="primary" loading={reset.isPending} className="w-full">
            Update password
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
