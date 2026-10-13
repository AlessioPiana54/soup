/**
 * InputFormatPlugin - the interface every input format implements,
 * mirroring the backend's InputReader contract. `kind` groups formats
 * that feed the same pipeline (e.g. "event_log"); a page only asks the
 * registry for formats of the kind it knows how to handle.
 */
export interface InputFormatPlugin {
  readonly id: string;
  readonly label: string;
  readonly extensions: readonly string[];
  readonly kind: string;

  /** Whether this format can read `file` (default implementations match by extension). */
  accepts(file: File): boolean;
}
