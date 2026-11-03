import { data, Link } from "react-router";

import { getAuth, LOGIN_PATH } from "~/.server/auth/session";
import { AuthPage } from "~/components/auth-page";

import type { Route } from "./+types/auth.logout";

export function meta() {
  return [{ title: "Abgemeldet · Finanzfuchs" }];
}

export async function action({ request }: Route.ActionArgs) {
  const { sessions } = getAuth();
  const session = await sessions.getSession(request.headers.get("Cookie"));
  return data(null, { headers: { "Set-Cookie": await sessions.destroySession(session) } });
}

export default function LoggedOut() {
  return (
    <AuthPage title="Abgemeldet">
      <p>Bis zum nächsten Mal.</p>
      <Link to={LOGIN_PATH} reloadDocument className="font-semibold text-fox">
        Wieder anmelden
      </Link>
    </AuthPage>
  );
}
