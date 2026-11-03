import type { IdentityProvider, PendingLogin } from "./identity-provider";

export interface SessionUser {
  subject: string;
  name: string;
}

/** A login cannot go on; the message is for the log, not for the page. */
export class LoginRejectedError extends Error {
  override name = "LoginRejectedError";
}

/** Only members of the family group get in. */
export async function finishLogin(
  provider: IdentityProvider,
  callback: URL,
  pending: PendingLogin | undefined,
  allowedGroup: string,
): Promise<SessionUser> {
  if (!pending) {
    throw new LoginRejectedError("No login was started in this browser");
  }
  const login = await verifiedLogin(provider, callback, pending);
  if (!login.groups.includes(allowedGroup)) {
    throw new LoginRejectedError(`${login.subject} is not in group ${allowedGroup}`);
  }
  return { subject: login.subject, name: login.name ?? login.subject };
}

async function verifiedLogin(provider: IdentityProvider, callback: URL, pending: PendingLogin) {
  try {
    return await provider.finishLogin(callback, pending);
  } catch (error) {
    throw new LoginRejectedError(`Pocket ID login failed: ${describe(error)}`);
  }
}

/** openid-client puts the provider's own answer into `error` and `error_description`. */
function describe(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (typeof error !== "object" || error === null) {
    return message;
  }
  const answer = [Reflect.get(error, "error"), Reflect.get(error, "error_description")].filter((part) => typeof part === "string");
  return answer.length > 0 ? `${message} (${answer.join(": ")})` : message;
}
