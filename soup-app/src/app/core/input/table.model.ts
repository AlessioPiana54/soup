/**
 * Table - the plain, text-only shape an input format's preview is built
 * from. Every cell is a string or null: no parsing/typing happens on the
 * frontend, the backend owns normalization (spaces, millisecond commas,
 * mapping validation) once a format is imported.
 */
export interface Table {
  columns: string[];
  rows: (string | null)[][];
}
