import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { ApiError, errorMessage, fieldError } from "@/api/client";
import { auth, qk } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { ProviderButtons } from "@/components/ProviderButtons";
import { Button, Callout, Input, TextLink } from "@/components/ui";
import { safeNext } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { oauthErrorMessage } from "@/lib/messages";

export default function Login() {
  usePageMeta([{ label: "Sign in" }]);
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [redirectError, setRedirectError] = useState(() => oauthErrorMessage(params.get("error")));
  const navigate = useNavigate();
  const qc = useQueryClient();

  const login = useMutation({
    mutationFn: () => auth.login({ email, password }),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: qk.me });
      await qc.refetchQueries({ queryKey: qk.me });
      navigate(next, { replace: true });
    },
  });
  const resend = useMutation({ mutationFn: () => auth.resendVerification(email) });
  const unverified = login.error instanceof ApiError && login.error.code === "email_not_verified";

  return (
    <AuthCard
      title="Sign in"
      subtitle={
        <>
          New here? <TextLink to={`/signup${next !== "/app" ? `?next=${encodeURIComponent(next)}` : ""}`}>Create an account</TextLink>
        </>
      }
    >
      {redirectError && (
        <Callout tone="danger" className="mb-4" onDismiss={() => setRedirectError(null)}>
          {redirectError}
        </Callout>
      )}
      <ProviderButtons next={next} />
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          login.mutate();
        }}
      >
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldError(login.error, "email")}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aside={
            <Link to="/forgot-password" className="text-fg-subtle transition-colors hover:text-fg">
              Forgot?
            </Link>
          }
        />
        {login.isError && (
          <Callout
            tone={unverified ? "warning" : "danger"}
            action={
              unverified && (
                <Button size="xs" variant="ghost" loading={resend.isPending} disabled={resend.isSuccess} onClick={() => resend.mutate()}>
                  {resend.isSuccess ? "Sent" : "Resend email"}
                </Button>
              )
            }
          >
            {errorMessage(login.error)}
          </Callout>
        )}
        <Button type="submit" variant="primary" loading={login.isPending} className="mt-1 w-full">
          Sign in
        </Button>
      </form>
    </AuthCard>
  );
}
