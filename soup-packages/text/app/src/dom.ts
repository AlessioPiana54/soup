/**
 * DOM helpers of the text package (h() and errorMessage() come from
 * @soup/sdk). Text coming from data is always set with textContent.
 */

/** "1.2 KB": a size in bytes for people. */
export function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB'];
  let value = bytes / 1024;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit++;
  }
  return `${value.toFixed(1)} ${units[unit]}`;
}

