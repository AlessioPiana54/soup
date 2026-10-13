import { InputFormatPlugin } from './input-format-plugin';

/**
 * ExtensionBasedInputFormat - base class for formats that decide whether
 * they accept a file purely by its extension (the common case). Plugins
 * only need to declare `extensions`; `accepts()` is implemented once.
 */
export abstract class ExtensionBasedInputFormat implements InputFormatPlugin {
  public abstract readonly id: string;
  public abstract readonly label: string;
  public abstract readonly extensions: readonly string[];
  public abstract readonly kind: string;

  public accepts(file: File): boolean {
    const name = file.name.toLowerCase();
    return this.extensions.some((extension) => name.endsWith(extension.toLowerCase()));
  }
}
