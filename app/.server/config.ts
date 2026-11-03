/** Settings from the environment: the untracked `.env` locally, the container env on the Pi. */
export interface AuthSettings {
  baseUrl: string;
  issuer: string;
  clientId: string;
  clientSecret: string;
  allowedGroup: string;
  sessionSecret: string;
}

export class ConfigError extends Error {
  override name = "ConfigError";
}

const REQUIRED_VARIABLES = ["FINANZFUCHS_BASE_URL", "OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "SESSION_SECRET"] as const;
const DEFAULT_ALLOWED_GROUP = "fuxbau";
// The secret signs the session cookie; a short one could be guessed.
const MIN_SESSION_SECRET_LENGTH = 32;

export const CALLBACK_PATH = "/auth/callback";

export function readAuthSettings(environment: Record<string, string | undefined> = process.env): AuthSettings {
  const missing = REQUIRED_VARIABLES.filter((name) => !environment[name]);
  if (missing.length > 0) {
    throw new ConfigError(`Missing settings: ${missing.join(", ")} (see .env.example)`);
  }
  const sessionSecret = environment.SESSION_SECRET!;
  if (sessionSecret.length < MIN_SESSION_SECRET_LENGTH) {
    throw new ConfigError(`SESSION_SECRET needs at least ${MIN_SESSION_SECRET_LENGTH} characters`);
  }
  return {
    baseUrl: environment.FINANZFUCHS_BASE_URL!.replace(/\/+$/, ""),
    issuer: environment.OIDC_ISSUER!,
    clientId: environment.OIDC_CLIENT_ID!,
    clientSecret: environment.OIDC_CLIENT_SECRET!,
    allowedGroup: environment.OIDC_ALLOWED_GROUP || DEFAULT_ALLOWED_GROUP,
    sessionSecret,
  };
}

export function callbackUrl(settings: AuthSettings): string {
  return `${settings.baseUrl}${CALLBACK_PATH}`;
}

export function usesHttps(settings: AuthSettings): boolean {
  return settings.baseUrl.startsWith("https://");
}
