import { createContext, createCookieSessionStorage, type MiddlewareFunction, redirect, type SessionStorage } from "react-router";

import { type AuthSettings, readAuthSettings, usesHttps } from "~/.server/config";

import { type IdentityProvider, type PendingLogin, PocketId } from "./identity-provider";
import type { SessionUser } from "./login";

export const LOGIN_PATH = "/auth/login";
const SESSION_LIFETIME_SECONDS = 30 * 24 * 60 * 60;

interface SessionData {
  user: SessionUser;
}

interface FlashData {
  pendingLogin: PendingLogin;
}

export type LoginSessionStorage = SessionStorage<SessionData, FlashData>;

/**
 * A signed, HttpOnly, SameSite=Lax cookie: it is not sent on cross-site POSTs, which covers CSRF
 * for the forms. It holds only who is logged in, never a token of the provider.
 */
export function createLoginSessionStorage(settings: AuthSettings): LoginSessionStorage {
  return createCookieSessionStorage<SessionData, FlashData>({
    cookie: {
      name: "finanzfuchs_session",
      httpOnly: true,
      sameSite: "lax",
      secure: usesHttps(settings),
      path: "/",
      maxAge: SESSION_LIFETIME_SECONDS,
      secrets: [settings.sessionSecret],
    },
  });
}

interface Auth {
  settings: AuthSettings;
  sessions: LoginSessionStorage;
  provider: IdentityProvider;
}

let auth: Auth | undefined;

/** Read on first use, so building and testing the app need no login settings. */
export function getAuth(): Auth {
  if (!auth) {
    const settings = readAuthSettings();
    auth = { settings, sessions: createLoginSessionStorage(settings), provider: new PocketId(settings) };
  }
  return auth;
}

export const userContext = createContext<SessionUser>();

/** Every page and every form below the layout needs a logged-in member of the family. */
export function requireUser(sessions: () => LoginSessionStorage): MiddlewareFunction<Response> {
  return async ({ request, context }, next) => {
    const session = await sessions().getSession(request.headers.get("Cookie"));
    const user = session.get("user");
    if (!user) {
      throw redirect(LOGIN_PATH);
    }
    context.set(userContext, user);
    return next();
  };
}
