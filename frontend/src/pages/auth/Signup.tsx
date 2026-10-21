import { useMutation } from "@tanstack/react-query";
import { MailCheck } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router";
import { errorMessage, fieldError } from "@/api/client";
import { auth } from "@/api/endpoints";
import { AuthCard } from "@/components/layout/PublicLayout";
import { ProviderButtons } from "@/components/ProviderButtons";
import { Button, Callout, EmptyState, Input, TextLink } from "@/components/ui";
import { safeNext } from "@/hooks/useMe";
import { usePageMeta } from "@/hooks/usePageMeta";
import { MIN_PASSWORD } from "@/lib/labels";

export default function Signup() {
  usePageMeta([{ label: "Create account" }]);
  const [params] = useSearchParams();
  const next = safeNext(params.get("next"));
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState(false);
  const signup = useMutation({ mutationFn: () => auth.signup({ email, password, name: name.trim() || null }) });
  const tooShort = password.length > 0 && password.length < MIN_PASSWORD;

  if (signup.isSuccess) {
    return (
      <AuthCard title="Check your email">
        <EmptyState
          compact
          icon={<MailCheck />}
          title={<span>We sent a link to <strong>{email}</strong></span>}
          info="Open it within 24 hours to verify your address. Already have an account? We emailed you instead."
          action={<TextLink to="/login">Back to sign in</TextLink>}
        />
      </AuthCard>
    );
  }

  return (
    <AuthCard
      title="Create account"
      subtitle={
        <>
          Have one? <TextLink to="/login">Sign in</TextLink>
        </>
      }
    >
      <ProviderButtons next={next} label="Sign up with" />
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setTouched(true);
          if (password.length >= MIN_PASSWORD) signup.mutate();
        }}
      >
        <Input label="Name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={fieldError(signup.error, "email")}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          info={`At least ${MIN_PASSWORD} characters. Common passwords are rejected.`}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched(true)}
          maxLength={128}
          error={(touched && tooShort ? `At least ${MIN_PASSWORD} characters.` : null) ?? fieldError(signup.error, "password")}
        />
        {signup.isError && !fieldError(signup.error, "email") && <Callout tone="danger">{errorMessage(signup.error)}</Callout>}
        <Button type="submit" variant="primary" loading={signup.isPending} className="mt-1 w-full">
          Create account
        </Button>
      </form>
    </AuthCard>
  );
}
