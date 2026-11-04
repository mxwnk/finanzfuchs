import { useState } from "react";
import { Form, Link, useNavigation } from "react-router";

import {
  addTransactions,
  assignAutomatically,
  assignedSpending,
  countUnassignedSpending,
  type Database,
  getDatabase,
  unassignedSpending,
} from "~/.server/database";
import { Card } from "~/components/ui";
import { DkbExportError, parseDkbExport } from "~/domain/dkb-export.server";
import { learnAssignments } from "~/domain/learned-assignment";

import type { Route } from "./+types/import";

export function meta() {
  return [{ title: "Import · Finanzfuchs" }];
}

export async function action({ request }: Route.ActionArgs) {
  const file = (await request.formData()).get("file");
  if (!(file instanceof File) || file.size === 0) {
    return { error: "Bitte eine CSV-Datei auswählen." };
  }
  try {
    const parsed = parseDkbExport(await file.text());
    const database = getDatabase();
    const added = addTransactions(database, parsed.transactions);
    return {
      summary: {
        fileName: file.name,
        added,
        known: parsed.transactions.length - added,
        pending: parsed.pendingCount,
        assignedAutomatically: assignFromHistory(database),
        stillOpen: countUnassignedSpending(database),
      },
    };
  } catch (error) {
    if (error instanceof DkbExportError) {
      return { error: `Die Datei ist kein DKB-Umsatzexport: ${error.message}` };
    }
    throw error;
  }
}

/** Earlier payments teach the categories of new ones; whatever stays unclear waits on Zuordnen. */
function assignFromHistory(database: Database): number {
  return assignAutomatically(database, learnAssignments(unassignedSpending(database), assignedSpending(database)));
}

export default function ImportPage({ actionData }: Route.ComponentProps) {
  const [fileName, setFileName] = useState<string | null>(null);
  const isImporting = useNavigation().state === "submitting";
  return (
    <div className="space-y-4">
      <Card>
        <h3 className="font-semibold">DKB-Umsätze hochladen</h3>
        <p className="mb-4 text-sm text-stone-500">
          Im DKB-Banking: Konto → Umsätze → Zeitraum wählen → Export als CSV. Überschneidende Zeiträume sind kein Problem,
          bekannte Buchungen werden übersprungen.
        </p>
        <Form method="post" encType="multipart/form-data" className="space-y-3">
          <label className="grid cursor-pointer place-items-center gap-1 rounded-2xl border-2 border-dashed border-stone-300 px-4 py-10 text-center hover:border-fox hover:bg-fox/5 dark:border-stone-700">
            <span className="text-2xl" aria-hidden>⬆</span>
            <span className="font-semibold">CSV-Datei wählen</span>
            <span className="text-sm text-stone-500">{fileName ?? "noch keine Datei"}</span>
            <input
              type="file"
              name="file"
              accept=".csv,text/csv"
              required
              className="sr-only"
              onChange={(event) => setFileName(event.target.files?.[0]?.name ?? null)}
            />
          </label>
          <button
            type="submit"
            disabled={isImporting}
            className="w-full rounded-xl bg-fox px-5 py-3 font-semibold text-white shadow-sm hover:brightness-105 disabled:opacity-60"
          >
            {isImporting ? "Importiere …" : "Importieren"}
          </button>
        </Form>
      </Card>

      {actionData && "error" in actionData && (
        <Card className="border-red-300 bg-red-50 text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200">{actionData.error}</Card>
      )}

      {actionData && "summary" in actionData && actionData.summary && (
        <Card>
          <h3 className="font-semibold">Importiert: {actionData.summary.fileName}</h3>
          <dl className="mt-3 grid grid-cols-3 gap-3 text-center">
            <Stat label="neu" value={actionData.summary.added} />
            <Stat label="schon bekannt" value={actionData.summary.known} />
            <Stat label="vorgemerkt" value={actionData.summary.pending} />
          </dl>
          <p className="mt-4 text-sm text-stone-500">
            {actionData.summary.assignedAutomatically} automatisch zugeordnet wie frühere Zahlungen,{" "}
            {actionData.summary.stillOpen} warten noch auf eine Kategorie.
          </p>
          {actionData.summary.assignedAutomatically + actionData.summary.stillOpen > 0 && (
            <Link to="/zuordnen" className="mt-4 block rounded-xl bg-stone-900 px-5 py-3 text-center font-semibold text-white dark:bg-white dark:text-stone-900">
              Prüfen und zuordnen →
            </Link>
          )}
        </Card>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dd className="num text-3xl font-bold">{value}</dd>
      <dt className="text-xs text-stone-500">{label}</dt>
    </div>
  );
}
