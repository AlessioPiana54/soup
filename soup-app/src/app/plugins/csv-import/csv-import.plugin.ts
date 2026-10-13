import { SoupFrontendPlugin } from '../../core/plugins/soup-frontend-plugin';
import { CsvImportFormat } from './csv-import-format';

/** The built-in CSV plugin, registered in app.config.ts via provideSoupPlugins(csvImportPlugin). */
export const csvImportPlugin: SoupFrontendPlugin = {
  id: 'csv_import',
  inputFormats: [new CsvImportFormat()]
};
