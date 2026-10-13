import { InputFormatPlugin } from './input-format-plugin';
import { Table } from './table.model';

/** The only input kind the page currently has a UI for. */
export const EVENT_LOG_KIND = 'event_log';

/**
 * EventLogFormatPlugin - an InputFormatPlugin of kind "event_log".
 * `readPreview` always returns a flat Table, regardless of the
 * underlying file's real shape: the preview exists only to let the user
 * pick which columns are the event id, timestamp and activity, not to
 * reproduce the exact data the backend will build the graph from.
 */
export interface EventLogFormatPlugin extends InputFormatPlugin {
  readonly kind: typeof EVENT_LOG_KIND;

  readPreview(file: File): Promise<Table>;
}
