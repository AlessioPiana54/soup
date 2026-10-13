import { InputFormatPlugin } from '../input/input-format-plugin';

/**
 * SoupFrontendPlugin - a bundle of contributions a plugin registers with
 * the app via provideSoupPlugins(). Only `inputFormats` exists today
 * (Pilastro 1); future pilastri would add `filters`/`graphRenderers` the
 * same way, without this interface's existing shape changing.
 */
export interface SoupFrontendPlugin {
  readonly id: string;
  readonly inputFormats?: InputFormatPlugin[];
}
