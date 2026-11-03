import { Card } from "./ui";

/** The pages around the login: logged out, access denied. */
export function AuthPage({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-md px-4 pt-16">
      <Card className="space-y-3 text-center">
        <p className="text-4xl" aria-hidden>🦊</p>
        <h1 className="text-xl font-bold">{title}</h1>
        {children}
      </Card>
    </main>
  );
}
