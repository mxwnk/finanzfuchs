import { type MiddlewareFunction, RouterContextProvider } from "react-router";
import { describe, expect, it } from "vitest";

import { readAuthSettings } from "~/.server/config";

import { LOGIN_PATH } from "~/auth-paths";

import { createLoginSessionStorage, requireUser, userContext } from "./session";

const sessions = createLoginSessionStorage(
  readAuthSettings({
    FINANZFUCHS_BASE_URL: "http://finanzfuchs.test",
    OIDC_ISSUER: "https://id.example.test",
    OIDC_CLIENT_ID: "client",
    OIDC_CLIENT_SECRET: "secret",
    SESSION_SECRET: "a".repeat(32),
  }),
);
const middleware = requireUser(() => sessions);
const PAGE = new Response("page");

async function run(cookie: string | null) {
  const request = new Request("http://finanzfuchs.test/budgets", { headers: cookie ? { Cookie: cookie } : {} });
  const context = new RouterContextProvider();
  const args = { request, context, params: {} } as unknown as Parameters<MiddlewareFunction<Response>>[0];
  try {
    return { response: (await middleware(args, async () => PAGE)) as Response, context };
  } catch (thrown) {
    return { response: thrown as Response, context };
  }
}

async function cookieOf(user: { subject: string; name: string }): Promise<string> {
  const session = await sessions.getSession();
  session.set("user", user);
  return (await sessions.commitSession(session)).split(";")[0];
}

describe("requireUser", () => {
  it("sends a visitor without a session to the login", async () => {
    const { response } = await run(null);

    expect(response.headers.get("Location")).toBe(LOGIN_PATH);
  });

  it("lets a logged-in user through and tells the page who it is", async () => {
    const { response, context } = await run(await cookieOf({ subject: "max", name: "Max" }));

    expect(response).toBe(PAGE);
    expect(context.get(userContext).name).toBe("Max");
  });

  it("does not trust a cookie with a forged signature", async () => {
    const cookie = await cookieOf({ subject: "max", name: "Max" });
    const forged = cookie.replace(/\.[^.]+$/, ".forged");

    const { response } = await run(forged);

    expect(response.headers.get("Location")).toBe(LOGIN_PATH);
  });
});
