import * as oidc from "openid-client";

import { type AuthSettings, callbackUrl } from "~/.server/config";

/** What the browser keeps (in the signed session cookie) while the user is at Pocket ID. */
export interface PendingLogin {
  state: string;
  nonce: string;
  codeVerifier: string;
}

export interface LoginRequest {
  authorizationUrl: string;
  pending: PendingLogin;
}

export interface VerifiedLogin {
  subject: string;
  name: string | null;
  groups: string[];
}

export interface IdentityProvider {
  startLogin(): Promise<LoginRequest>;
  /** Verifies the provider's answer: state, PKCE, nonce and the signed ID token. */
  finishLogin(callback: URL, pending: PendingLogin): Promise<VerifiedLogin>;
}

// `groups` makes Pocket ID put the user's group names into the ID token.
const SCOPES = "openid profile email groups";

/** Pocket ID through OpenID Connect: authorization code flow with PKCE and a verified ID token. */
export class PocketId implements IdentityProvider {
  private configuration: Promise<oidc.Configuration> | undefined;

  constructor(private readonly settings: AuthSettings) {}

  async startLogin(): Promise<LoginRequest> {
    const pending = { state: oidc.randomState(), nonce: oidc.randomNonce(), codeVerifier: oidc.randomPKCECodeVerifier() };
    const url = oidc.buildAuthorizationUrl(await this.discover(), {
      redirect_uri: callbackUrl(this.settings),
      scope: SCOPES,
      state: pending.state,
      nonce: pending.nonce,
      code_challenge: await oidc.calculatePKCECodeChallenge(pending.codeVerifier),
      code_challenge_method: "S256",
    });
    return { authorizationUrl: url.href, pending };
  }

  async finishLogin(callback: URL, pending: PendingLogin): Promise<VerifiedLogin> {
    const tokens = await oidc.authorizationCodeGrant(await this.discover(), callback, {
      pkceCodeVerifier: pending.codeVerifier,
      expectedState: pending.state,
      expectedNonce: pending.nonce,
      idTokenExpected: true,
    });
    const claims = tokens.claims();
    if (!claims) {
      throw new Error("Pocket ID answered without an ID token");
    }
    return { subject: claims.sub, name: typeof claims.name === "string" ? claims.name : null, groups: groupsFrom(claims.groups) };
  }

  /**
   * Discovery is fetched once; a failed attempt is retried on the next login. The secret goes in
   * the form body: for Basic auth openid-client encodes the `-` of the client id as `%2D`, which
   * Pocket ID does not decode and answers "Record not found".
   */
  private discover(): Promise<oidc.Configuration> {
    this.configuration ??= oidc
      .discovery(new URL(this.settings.issuer), this.settings.clientId, undefined, oidc.ClientSecretPost(this.settings.clientSecret))
      .catch((error: unknown) => {
        this.configuration = undefined;
        throw error;
      });
    return this.configuration;
  }
}

function groupsFrom(claim: unknown): string[] {
  return Array.isArray(claim) ? claim.map(String) : [];
}
