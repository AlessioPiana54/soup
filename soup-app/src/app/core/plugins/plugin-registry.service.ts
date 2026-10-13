import { Inject, Injectable, Optional } from '@angular/core';

import { InputFormatPlugin } from '../input/input-format-plugin';
import { INPUT_FORMAT_PLUGINS } from './plugin-tokens';

/**
 * PluginRegistryService - the frontend's equivalent of the backend
 * Registry: pages ask it for "the formats of this kind" instead of
 * importing a concrete format implementation.
 */
@Injectable({
  providedIn: 'root'
})
export class PluginRegistryService {
  /**
   * Initialize a new instance of PluginRegistryService service
   * @param inputFormatPlugins every InputFormatPlugin registered via provideSoupPlugins()
   */
  constructor(@Optional() @Inject(INPUT_FORMAT_PLUGINS) private readonly inputFormatPlugins: InputFormatPlugin[] | null) {}

  /**
   * Find the registered format (of `kind`, if given) that accepts `file`.
   * @param file the file to match
   * @param kind restrict the search to formats of this kind
   * @returns the matching InputFormatPlugin, or undefined if none accepts the file
   */
  public inputFormatFor<T extends InputFormatPlugin = InputFormatPlugin>(file: File, kind?: string): T | undefined {
    return this.formatsOf(kind).find((format) => format.accepts(file)) as T | undefined;
  }

  /**
   * The extensions every registered format (of `kind`, if given) accepts,
   * de-duplicated - used to build the drop zone's `accept` attribute.
   * @param kind restrict the result to formats of this kind
   * @returns the accepted extensions
   */
  public acceptedExtensions(kind?: string): string[] {
    const extensions = this.formatsOf(kind).flatMap((format) => [...format.extensions]);
    return Array.from(new Set(extensions));
  }

  /**
   * Every registered format, optionally restricted to `kind`.
   * @param kind restrict the result to formats of this kind
   */
  private formatsOf(kind?: string): InputFormatPlugin[] {
    const all = this.inputFormatPlugins ?? [];
    return kind ? all.filter((format) => format.kind === kind) : all;
  }
}
