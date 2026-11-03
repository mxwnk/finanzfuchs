/** Server log lines with time and level on stdout, where Docker collects them. */
type Level = "info" | "warn" | "error";

const WRITERS: Record<Level, (...parts: unknown[]) => void> = {
  info: console.info,
  warn: console.warn,
  error: console.error,
};

function write(level: Level, message: string, details?: unknown): void {
  const line = `${new Date().toISOString()} ${level.toUpperCase()} ${message}`;
  WRITERS[level](...(details === undefined ? [line] : [line, details]));
}

export const logger = {
  info: (message: string) => write("info", message),
  warn: (message: string, details?: unknown) => write("warn", message, details),
  error: (message: string, details?: unknown) => write("error", message, details),
};
