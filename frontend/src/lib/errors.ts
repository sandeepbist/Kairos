/** Type-safe helpers shared across the dashboard. */

/** Extracts a human-readable message from unknown thrown values. */
export function errorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "string" && err) return err;
  return fallback;
}
