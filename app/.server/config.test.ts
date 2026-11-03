import { describe, expect, it } from "vitest";

import { callbackUrl, ConfigError, readAuthSettings } from "./config";

const ENVIRONMENT = {
  FINANZFUCHS_BASE_URL: "http://finanzfuchs.test/",
  OIDC_ISSUER: "https://id.example.test",
  OIDC_CLIENT_ID: "client",
  OIDC_CLIENT_SECRET: "secret",
  SESSION_SECRET: "a".repeat(32),
};

describe("readAuthSettings", () => {
  it("reads the login settings and defaults the family group", () => {
    const settings = readAuthSettings(ENVIRONMENT);

    expect(settings).toMatchObject({ issuer: "https://id.example.test", clientId: "client", allowedGroup: "fuxbau" });
  });

  it("builds the callback address without a doubled slash", () => {
    const settings = readAuthSettings(ENVIRONMENT);

    expect(callbackUrl(settings)).toBe("http://finanzfuchs.test/auth/callback");
  });

  it("names every missing setting", () => {
    const { OIDC_CLIENT_ID, SESSION_SECRET, ...incomplete } = ENVIRONMENT;

    expect(() => readAuthSettings(incomplete)).toThrow(/OIDC_CLIENT_ID, SESSION_SECRET/);
  });

  it("refuses a session secret that is too short to be safe", () => {
    expect(() => readAuthSettings({ ...ENVIRONMENT, SESSION_SECRET: "short" })).toThrow(ConfigError);
  });
});
