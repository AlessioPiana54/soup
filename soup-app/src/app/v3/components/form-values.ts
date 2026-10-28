import { Field, FieldType, FileValue, FormValues, ItemValue, LIST_FIELD_TYPES, PairValue, Variant } from '@soup/sdk';

/**
 * The values of a soup-dynamic-form, as plain functions: the initial
 * values of a form, what counts as empty, the required-field errors and
 * the one-line summary of an "items" element (its tile). The values have
 * the shapes soup/core/field_validation.py accepts.
 */

const REQUIRED_MESSAGE = 'Campo obbligatorio';

const SUMMARY_MAX = 120;

/** A deep copy, so a default or a value given by the parent is never mutated. */
function copy<T>(value: T): T {
  return value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T);
}

// The value of an empty field, per type (a list for the list types, '' for the others).
const EMPTY_VALUES: Partial<Record<FieldType, () => unknown>> = {
  bool: () => false,
  number: () => null,
  file: () => null
};

function emptyValue(field: Field): unknown {
  if (LIST_FIELD_TYPES.includes(field.type)) {
    return [];
  }
  return (EMPTY_VALUES[field.type] ?? (() => ''))();
}

/** Every field's value: the one given, else its default, else its empty value. */
export function initialValues(fields: readonly Field[], given: FormValues | null | undefined): FormValues {
  const values: FormValues = {};
  for (const field of fields) {
    if (given && given[field.name] !== undefined) {
      values[field.name] = copy(given[field.name]);
    } else if (field.default !== null && field.default !== undefined) {
      values[field.name] = copy(field.default);
    } else {
      values[field.name] = emptyValue(field);
    }
  }
  return values;
}

function isEmpty(field: Field, value: unknown): boolean {
  if (value === null || value === undefined) {
    return true;
  }
  if (typeof value === 'string') {
    return value.trim() === '';
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  return field.type === 'number' && typeof value === 'number' && Number.isNaN(value);
}

/** {field name: message} for the required fields without a value. */
export function requiredErrors(fields: readonly Field[], values: FormValues): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields) {
    if (field.required && field.type !== 'bool' && isEmpty(field, values[field.name])) {
      errors[field.name] = REQUIRED_MESSAGE;
    }
  }
  return errors;
}

/** The value of one field as short text. */
export function formatValue(field: Field, value: unknown): string {
  if (isEmpty(field, value)) {
    return '-';
  }
  return (FORMATTERS[field.type] ?? plainText)(field, value);
}

type Formatter = (field: Field, value: unknown) => string;

function plainText(_field: Field, value: unknown): string {
  return Array.isArray(value) ? value.join(', ') : String(value);
}

function choiceLabel(field: Field, value: unknown): string {
  return field.choices.find((choice) => choice.value === value)?.label ?? String(value);
}

// The short text of a value, per type (plainText for the others).
const FORMATTERS: Partial<Record<FieldType, Formatter>> = {
  bool: (_field, value) => (value ? 'sì' : 'no'),
  pairs: (_field, value) => (value as PairValue[]).map(([first, second]) => `${first} → ${second}`).join(', '),
  file: (_field, value) => (value as FileValue).filename,
  items: (_field, value) => `${(value as ItemValue[]).length} elementi`,
  select: choiceLabel,
  multiselect: (field, value) => (value as string[]).map((item) => choiceLabel(field, item)).join(', ')
};

/** The text of the tile of an "items" element: "field: value; ...". */
export function summarize(variant: Variant | undefined, item: ItemValue): string {
  if (!variant) {
    return `Variante sconosciuta '${item.variant}'`;
  }
  const parts = variant.fields.map((field) => `${field.label}: ${formatValue(field, item.values[field.name])}`);
  const text = parts.join('; ') || variant.description || variant.label;
  return text.length > SUMMARY_MAX ? `${text.slice(0, SUMMARY_MAX - 1)}…` : text;
}

/** The new list without the element at `index` (the value itself changes, not only the view). */
export function withoutIndex<T>(list: readonly T[], index: number): T[] {
  return list.filter((_, position) => position !== index);
}

/** The options of a column/columns/pairs field: its choices, else the preview's columns. */
export function optionsFor(field: Field, columns: readonly string[]): { value: string; label: string }[] {
  if (field.choices.length) {
    return field.choices;
  }
  return columns.map((column) => ({ value: column, label: column }));
}

/** A file chosen by the user as the JSON value of a "file" field. */
export function readFileValue(file: File): Promise<FileValue> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(reader.error ?? new Error(`Cannot read ${file.name}`));
    reader.onload = () => {
      const url = String(reader.result ?? '');
      resolve({ filename: file.name, base64: url.slice(url.indexOf(',') + 1), content_type: file.type || undefined });
    };
    reader.readAsDataURL(file);
  });
}
