/**
 * defineSoupElement - registers a package's custom element once. The host
 * may import a package bundle again (after enable/disable, or a second
 * bundle defining the same tag): a tag already defined is left alone
 * instead of throwing, because the browser cannot redefine it.
 */

// The custom element name rules of the HTML standard, restricted to ASCII.
const ELEMENT_NAME_RE = /^[a-z][a-z0-9._]*-[a-z0-9._-]*$/;

const RESERVED_NAMES = new Set([
  'annotation-xml',
  'color-profile',
  'font-face',
  'font-face-src',
  'font-face-uri',
  'font-face-format',
  'font-face-name',
  'missing-glyph'
]);

export function isValidElementName(tag: string): boolean {
  return ELEMENT_NAME_RE.test(tag) && !RESERVED_NAMES.has(tag);
}

/**
 * @returns true if the element was defined now, false if the tag already existed
 * @throws Error if `tag` is not a valid custom element name
 */
export function defineSoupElement(tag: string, klass: CustomElementConstructor, registry: CustomElementRegistry = customElements): boolean {
  if (!isValidElementName(tag)) {
    throw new Error(`Invalid custom element name '${tag}': lowercase, starting with a letter, with a '-'`);
  }
  const existing = registry.get(tag);
  if (existing) {
    if (existing !== klass) {
      console.warn(`[soup] <${tag}> is already defined; the new definition is ignored until the page is reloaded`);
    }
    return false;
  }
  registry.define(tag, klass);
  return true;
}
