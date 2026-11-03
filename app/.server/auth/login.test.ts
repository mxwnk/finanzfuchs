import { describe, expect, it } from "vitest";

import type { IdentityProvider, LoginRequest, PendingLogin, VerifiedLogin } from "./identity-provider";
import { finishLogin, LoginRejectedError } from "./login";

const PENDING: PendingLogin = { state: "state", nonce: "nonce", codeVerifier: "verifier" };
const CALLBACK = new URL("http://finanzfuchs.test/auth/callback?code=abc&state=state");

/** Answers like Pocket ID would, without the network. */
class FakePocketId implements IdentityProvider {
  constructor(private readonly answer: VerifiedLogin | Error) {}

  async startLogin(): Promise<LoginRequest> {
    return { authorizationUrl: "https://id.example.test/authorize", pending: PENDING };
  }

  async finishLogin(): Promise<VerifiedLogin> {
    if (this.answer instanceof Error) {
      throw this.answer;
    }
    return this.answer;
  }
}

describe("finishLogin", () => {
  it("lets a member of the family group in", async () => {
    const provider = new FakePocketId({ subject: "max", name: "Max", groups: ["fuxbau"] });

    const user = await finishLogin(provider, CALLBACK, PENDING, "fuxbau");

    expect(user).toEqual({ subject: "max", name: "Max" });
  });

  it("falls back to the subject when the provider sends no name", async () => {
    const provider = new FakePocketId({ subject: "max", name: null, groups: ["fuxbau"] });

    const user = await finishLogin(provider, CALLBACK, PENDING, "fuxbau");

    expect(user.name).toBe("max");
  });

  it("rejects someone outside the family group", async () => {
    const provider = new FakePocketId({ subject: "guest", name: "Gast", groups: ["friends"] });

    await expect(finishLogin(provider, CALLBACK, PENDING, "fuxbau")).rejects.toThrow(LoginRejectedError);
  });

  it("rejects a callback without a login started in this browser", async () => {
    const provider = new FakePocketId({ subject: "max", name: "Max", groups: ["fuxbau"] });

    await expect(finishLogin(provider, CALLBACK, undefined, "fuxbau")).rejects.toThrow(/No login was started/);
  });

  it("rejects an answer the provider could not verify", async () => {
    const provider = new FakePocketId(new Error("unexpected ID Token nonce claim value"));

    await expect(finishLogin(provider, CALLBACK, PENDING, "fuxbau")).rejects.toThrow(/nonce/);
  });
});
