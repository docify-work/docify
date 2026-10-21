// Friendly copy for error codes that arrive via redirects (?error=<code>).

export const OAUTH_ERRORS: Record<string, string> = {
  oauth_cancelled: "Sign-in was cancelled.",
  oauth_state: "That sign-in link expired. Please try again.",
  oauth_session: "Your session changed during sign-in. Please try again.",
  oauth_failed: "The provider didn't complete sign-in. Please try again.",
  provider_email_unverified: "Your email isn't verified with that provider. Verify it there, or use email and password.",
  identity_in_use: "That account is already linked to another Docify user.",
  provider_already_linked: "You already linked an account from this provider.",
  provider_disabled: "That sign-in method isn't available here.",
  login_required: "Please sign in first.",
  disabled: "This account is disabled.",
};

export const INSTALL_ERRORS: Record<string, string> = {
  install_not_yours: "That GitHub installation belongs to someone else. Ask its owner to connect it.",
  install_verify: "We couldn't verify the GitHub installation. Try connecting again.",
  install_missing: "The GitHub installation wasn't found. It may have been removed.",
  install_state: "The connect link expired. Start again from Repositories.",
  install_workspace: "The workspace for this installation no longer exists.",
};

export function oauthErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return OAUTH_ERRORS[code] ?? INSTALL_ERRORS[code] ?? "Something went wrong. Please try again.";
}

export function installErrorMessage(code: string | null): string | null {
  if (!code) return null;
  return INSTALL_ERRORS[code] ?? "Connecting GitHub failed. Please try again.";
}

export const PROVIDER_LABEL: Record<string, string> = { github: "GitHub", google: "Google" };
