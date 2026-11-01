import { createHash } from "node:crypto";

import { type Cents, parseGermanAmount } from "./money";

/** A booked transaction as the DKB online banking exports it ("Umsatzliste" as CSV). */
export interface BankTransaction {
  id: string;
  account: string;
  bookingDate: string;
  amountCents: Cents;
  counterparty: string;
  purpose: string;
}

export interface DkbExport {
  account: string;
  transactions: BankTransaction[];
  pendingCount: number;
}

export class DkbExportError extends Error {}

const HEADER_MARKER = '"Buchungsdatum"';
const BOOKED = "Gebucht";
const ID_PREFIX = "dkb-";

export function parseDkbExport(text: string): DkbExport {
  const lines = text.replace(/^﻿/, "").split(/\r?\n/);
  const account = readAccount(lines[0]);
  const headerIndex = lines.findIndex((line) => line.startsWith(HEADER_MARKER));
  if (headerIndex < 0) {
    throw new DkbExportError("Keine DKB-Umsatzliste: die Spaltenüberschrift „Buchungsdatum“ fehlt");
  }
  const columns = splitCsvLine(lines[headerIndex]);
  const seenFingerprints = new Map<string, number>();
  const transactions: BankTransaction[] = [];
  let pendingCount = 0;
  lines.slice(headerIndex + 1).forEach((line, offset) => {
    if (!line.trim()) return;
    const row = toRecord(columns, splitCsvLine(line));
    if (row["Status"] !== BOOKED) {
      pendingCount += 1;
      return;
    }
    transactions.push(readTransaction(row, account, headerIndex + offset + 2, seenFingerprints));
  });
  return { account, transactions, pendingCount };
}

function readAccount(firstLine: string | undefined): string {
  const [, iban] = splitCsvLine(firstLine ?? "");
  if (!iban) {
    throw new DkbExportError("Keine DKB-Umsatzliste: die erste Zeile nennt kein Konto");
  }
  return iban.replace(/\s/g, "");
}

function readTransaction(
  row: Record<string, string>,
  account: string,
  lineNumber: number,
  seenFingerprints: Map<string, number>,
): BankTransaction {
  let amountCents: Cents;
  try {
    amountCents = parseGermanAmount(row["Betrag (€)"] ?? "");
  } catch (error) {
    throw new DkbExportError(`Zeile ${lineNumber}: ${(error as Error).message}`);
  }
  const bookingDate = toIsoDate(row["Buchungsdatum"] ?? "", lineNumber);
  const counterparty = (amountCents < 0 ? row["Zahlungsempfänger*in"] : row["Zahlungspflichtige*r"]) ?? "";
  const purpose = (row["Verwendungszweck"] ?? "").replace(/\s+/g, " ").trim();
  const fingerprint = [account, bookingDate, counterparty, row["IBAN"], purpose, amountCents, row["Kundenreferenz"]].join("|");
  return {
    id: identify(fingerprint, seenFingerprints),
    account,
    bookingDate,
    amountCents,
    counterparty: counterparty.trim(),
    purpose,
  };
}

/** The export has no ids; identical rows of one day are told apart by their order in the file. */
function identify(fingerprint: string, seenFingerprints: Map<string, number>): string {
  const occurrence = seenFingerprints.get(fingerprint) ?? 0;
  seenFingerprints.set(fingerprint, occurrence + 1);
  const digest = createHash("sha256").update(`${fingerprint}|${occurrence}`).digest("hex");
  return ID_PREFIX + digest.slice(0, 16);
}

/** `30.10.26` → `2026-10-30`. */
function toIsoDate(text: string, lineNumber: number): string {
  const match = /^(\d{2})\.(\d{2})\.(\d{2})$/.exec(text);
  if (!match) {
    throw new DkbExportError(`Zeile ${lineNumber}: „${text}“ ist kein Datum`);
  }
  const [, day, month, year] = match;
  return `20${year}-${month}-${day}`;
}

function toRecord(columns: string[], values: string[]): Record<string, string> {
  return Object.fromEntries(columns.map((column, index) => [column, values[index] ?? ""]));
}

/** DKB quotes every field and separates with `;`; quotes inside a field are doubled. */
function splitCsvLine(line: string): string[] {
  const fields: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && quoted && line[index + 1] === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === ";" && !quoted) {
      fields.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  fields.push(current);
  return fields;
}
