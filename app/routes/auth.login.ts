import { redirect } from "react-router";

import { getAuth } from "~/.server/auth/session";

import type { Route } from "./+types/auth.login";

/** Off to Pocket ID; state, nonce and PKCE verifier wait in the session cookie. */
export async function loader({ request }: Route.LoaderArgs) {
  const { sessions, provider } = getAuth();
  const login = await provider.startLogin();
  const session = await sessions.getSession(request.headers.get("Cookie"));
  session.flash("pendingLogin", login.pending);
  return redirect(login.authorizationUrl, { headers: { "Set-Cookie": await sessions.commitSession(session) } });
}
