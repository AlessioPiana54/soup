// How long to wait for a loaded bundle to define a package's element
const ELEMENT_DEFINE_TIMEOUT_MS = 10000;

/**
 * Resolves when the custom element `tag` is defined; rejects after
 * `timeoutMs` (the bundle was loaded but does not define it).
 */
export function whenDefined(tag: string, timeoutMs = ELEMENT_DEFINE_TIMEOUT_MS): Promise<void> {
  if (customElements.get(tag)) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`The package bundle did not define <${tag}>`)), timeoutMs);
    customElements.whenDefined(tag).then(
      () => {
        clearTimeout(timer);
        resolve();
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      }
    );
  });
}
