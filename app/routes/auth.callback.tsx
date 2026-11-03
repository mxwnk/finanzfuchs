import { data, Link, redirect } from "react-router";

import { finishLogin, LoginRejectedError } from "~/.server/auth/login";
import { getAuth, LOGIN_PATH } from "~/.server/auth/session";
import { CALLBACK_PATH } from "~/.server/config";
import { logger } from "~/.server/logger";
import { AuthPage } from "~/components/auth-page";

import type { Route } from "./+types/auth.callback";

const FORBIDDEN = 403;

export function meta() {
  return [{ title: "Kein Zugang · Finanzfuchs" }];
}

/** Back from Pocket ID: a verified member of the family gets a session, everyone else a 403. */
export async function loader({ request }: Route.LoaderArgs) {
  const { settings, sessions, provider } = getAuth();
  const session = await sessions.getSession(request.headers.get("Cookie"));
  // The provider checks the redirect URI against the public address, not the container's.
  const callback = new URL(`${CALLBACK_PATH}${new URL(request.url).search}`, settings.baseUrl);
  try {
    const user = await finishLogin(provider, callback, session.get("pendingLogin"), settings.allowedGroup);
    session.set("user", user);
    logger.info(`Login of ${user.name}`);
    return redirect("/", { headers: { "Set-Cookie": await sessions.commitSession(session) } });
  } catch (error) {
    if (!(error instanceof LoginRejectedError)) {
      throw error;
    }
    logger.warn(`Login rejected: ${error.message}`);
    return data(null, { status: FORBIDDEN, headers: { "Set-Cookie": await sessions.commitSession(session) } });
  }
}

export default function LoginDenied() {
  return (
    <AuthPage title="Kein Zugang">
      <p>Die Anmeldung hat nicht geklappt, oder dein Konto gehört nicht zur Familie Fuxbau.</p>
      <Link to={LOGIN_PATH} reloadDocument className="font-semibold text-fox">
        Noch einmal anmelden
      </Link>
    </AuthPage>
  );
}
