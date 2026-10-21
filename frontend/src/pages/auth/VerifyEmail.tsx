import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router";
import { errorMessage } from "@/api/client";
import { auth, qk } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { Button, EmptyState, PageSpinner, TextLink } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function VerifyEmail() {
  usePageMeta([{ label: "Verify email" }]);
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const qc = useQueryClient();
  const verify = useMutation({
    mutationFn: () => auth.verifyEmail(token),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.me }),
  });
  // Tokens are single-use: make sure StrictMode's double effect doesn't post twice.
  const sent = useRef(false);
  const { mutate } = verify;
  useEffect(() => {
    if (token && !sent.current) {
      sent.current = true;
      mutate();
    }
  }, [token, mutate]);

  return (
    <AuthCard title="Verify email">
      {!token ? (
        <EmptyState compact icon={<XCircle className="text-danger" />} title="This link is missing its token." action={<TextLink to="/login">Sign in</TextLink>} />
      ) : verify.isSuccess ? (
        <EmptyState
          compact
          icon={<CheckCircle2 className="text-success" />}
          title="Email verified"
          action={
            <Button asChild variant="primary" size="sm">
              <Link to="/app">Continue</Link>
            </Button>
          }
        />
      ) : verify.isError ? (
        <EmptyState
          compact
          icon={<XCircle className="text-danger" />}
          title={errorMessage(verify.error)}
          info="Links expire after 24 hours. Sign in to get a new one."
          action={<TextLink to="/login">Sign in</TextLink>}
        />
      ) : (
        <PageSpinner label="Verifying" />
      )}
    </AuthCard>
  );
}
