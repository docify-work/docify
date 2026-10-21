import { oauthStartUrl } from "@/api/endpoints";
import { Button } from "@/components/ui";
import { useAppConfig } from "@/lib/config";
import { GitHubIcon, GoogleIcon } from "./BrandIcons";

/** "Continue with GitHub/Google" — plain navigations (OAuth redirect chain). Hidden when disabled. */
export function ProviderButtons({ next, label = "Continue with" }: { next: string; label?: string }) {
  const cfg = useAppConfig();
  if (!cfg.githubEnabled && !cfg.googleEnabled) return null;
  return (
    <>
      <div className="flex flex-col gap-2">
        {cfg.githubEnabled && (
          <Button asChild className="w-full">
            <a href={oauthStartUrl("github", "login", next)}>
              <GitHubIcon />
              {label} GitHub
            </a>
          </Button>
        )}
        {cfg.googleEnabled && (
          <Button asChild className="w-full">
            <a href={oauthStartUrl("google", "login", next)}>
              <GoogleIcon />
              {label} Google
            </a>
          </Button>
        )}
      </div>
      <div className="my-4 flex items-center gap-3 text-2xs uppercase tracking-wide text-fg-subtle">
        <span className="h-px flex-1 bg-border" />
        or
        <span className="h-px flex-1 bg-border" />
      </div>
    </>
  );
}
