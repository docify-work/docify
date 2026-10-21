import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { useState } from "react";
import { errorMessage } from "@/api/client";
import { auth } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { Button, Callout, EmptyState, Input, TextLink } from "@/components/ui";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function ForgotPassword() {
  usePageMeta([{ label: "Reset password" }]);
  const [email, setEmail] = useState("");
  const forgot = useMutation({ mutationFn: () => auth.forgotPassword(email) });

  return (
    <AuthCard title="Reset password" subtitle={<TextLink to="/login">Back to sign in</TextLink>}>
      {forgot.isSuccess ? (
        <EmptyState
          compact
          icon={<MailCheck />}
          title="Check your email"
          info="If an account exists for that address, a reset link is on its way. It expires in 1 hour."
        />
      ) : (
        <form
          className="flex flex-col gap-3"
          onSubmit={(e) => {
            e.preventDefault();
            forgot.mutate();
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
          />
          {forgot.isError && <Callout tone="danger">{errorMessage(forgot.error)}</Callout>}
          <Button type="submit" variant="primary" loading={forgot.isPending} className="w-full">
            Send reset link
          </Button>
        </form>
      )}
    </AuthCard>
  );
}
