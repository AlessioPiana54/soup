import { Papa } from 'ngx-papaparse';

import { EVENT_LOG_KIND, EventLogFormatPlugin } from '../../core/input/event-log-format-plugin';
import { ExtensionBasedInputFormat } from '../../core/input/extension-based-input-format';
import { Table } from '../../core/input/table.model';

/**
 * CsvImportFormat - reads a CSV file into a flat preview Table,
 * encapsulating Papa Parse so no other part of the page needs to know
 * it exists. Values are returned exactly as parsed (no space/timestamp
 * normalization): the backend now owns that, applied once regardless of
 * which format produced the data.
 */
export class CsvImportFormat extends ExtensionBasedInputFormat implements EventLogFormatPlugin {
  public readonly id = 'csv';
  public readonly label = 'CSV';
  public readonly kind = EVENT_LOG_KIND;
  public readonly extensions = ['.csv'];

  private readonly papa = new Papa();

  public readPreview(file: File): Promise<Table> {
    return new Promise<Table>((resolve, reject) => {
      this.papa.parse(file, {
        header: true,
        dynamicTyping: false,
        skipEmptyLines: true,
        complete: (results) => {
          const columns = results.meta.fields ?? [];
          const rows = (results.data as Record<string, string | null>[]).map((record) => columns.map((column) => record[column] ?? null));
          resolve({ columns, rows });
        },
        error: (error) => reject(error)
      });
    });
  }
}
