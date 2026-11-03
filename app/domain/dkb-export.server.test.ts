import { describe, expect, it } from "vitest";

import { DkbExportError, parseDkbExport } from "./dkb-export.server";

const ACCOUNT = "DE00111111110000000001";
const HEADER =
  `"Girokonto";"${ACCOUNT}"\n` +
  '"Zeitraum:";"01.10.2026 - 31.10.2026"\n' +
  '"Kontostand vom 31.10.2026:";"1.000,00 €"\n' +
  '""\n' +
  '"Buchungsdatum";"Wertstellung";"Status";"Zahlungspflichtige*r";"Zahlungsempfänger*in";' +
  '"Verwendungszweck";"Umsatztyp";"IBAN";"Betrag (€)";"Gläubiger-ID";"Mandatsreferenz";' +
  '"Kundenreferenz"\n';

function row(day: string, payee: string, amount: string, status = "Gebucht", payer = "ISSUER"): string {
  return `"${day}";"${day}";"${status}";"${payer}";"${payee}";"Einkauf";"Ausgang";"DE96";"${amount}";"";"";"ref"\n`;
}

function exportWith(...rows: string[]): string {
  return "﻿" + HEADER + rows.join("");
}

describe("parseDkbExport", () => {
  it("reads the account and booked transactions", () => {
    const result = parseDkbExport(exportWith(row("30.10.26", "REWE", "-20,30")));

    expect(result.account).toBe(ACCOUNT);
    expect(result.transactions).toEqual([
      expect.objectContaining({
        bookingDate: "2026-10-30",
        amountCents: -2030,
        counterparty: "REWE",
        purpose: "Einkauf",
      }),
    ]);
  });

  it("names the payer as counterparty of incoming money", () => {
    const salary = row("28.10.26", "Familie", "2.345,67", "Gebucht", "Arbeitgeber GmbH");

    const [transaction] = parseDkbExport(exportWith(salary)).transactions;

    expect(transaction.counterparty).toBe("Arbeitgeber GmbH");
    expect(transaction.amountCents).toBe(234567);
  });

  it("leaves out pending transactions and counts them", () => {
    const result = parseDkbExport(exportWith(row("31.10.26", "Lidl", "-5,00", "Vorgemerkt")));

    expect(result.transactions).toEqual([]);
    expect(result.pendingCount).toBe(1);
  });

  it("gives a row the same id in every export", () => {
    const first = parseDkbExport(exportWith(row("30.10.26", "REWE", "-20,30"), row("29.10.26", "IKEA", "-9,99")));
    const second = parseDkbExport(exportWith(row("30.10.26", "REWE", "-20,30")));

    expect(first.transactions[0].id).toBe(second.transactions[0].id);
  });

  it("tells identical rows of one day apart", () => {
    const [first, second] = parseDkbExport(
      exportWith(row("30.10.26", "REWE", "-20,30"), row("30.10.26", "REWE", "-20,30")),
    ).transactions;

    expect(first.id).not.toBe(second.id);
  });

  it("rejects a file that is no DKB export", () => {
    expect(() => parseDkbExport("Name;Betrag\nfoo;1\n")).toThrow(DkbExportError);
  });

  it("names the line of an unreadable amount", () => {
    expect(() => parseDkbExport(exportWith(row("30.10.26", "REWE", "viel")))).toThrow(/Zeile 6/);
  });
});
