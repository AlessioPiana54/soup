import { h } from '@soup/sdk';
import { base64Utf8, BlockElement } from '../dom';

type ImageData = { mime: string; base64: string; alt?: string } | { svg: string; alt?: string };

const CSS = `img { max-width: 100%; height: auto; } .error { color: #b02a37; }`;

/**
 * The URL of an image block for an <img src>: base64 content as a data:
 * URL of an image type, an SVG as a data: URL of image/svg+xml. An SVG
 * shown by <img> runs no script and loads nothing: its markup is never
 * inserted in the page.
 * @throws Error if the mime type is not an image type
 */
function imageUrl(data: ImageData): string {
  if ('svg' in data) {
    return `data:image/svg+xml;base64,${base64Utf8(String(data.svg))}`;
  }
  if (!/^image\/[a-z0-9.+-]+$/i.test(data.mime ?? '')) {
    throw new Error(`Not an image type: ${data.mime}`);
  }
  return `data:${data.mime};base64,${data.base64}`;
}

/** <soup-image>: `data` = {mime, base64} or {svg}. */
export class SoupImage extends BlockElement<ImageData> {
  protected override css(): string {
    return CSS;
  }

  protected draw(data: ImageData | undefined): Node[] {
    if (!data) return [];
    try {
      return [h('img', { attrs: { src: imageUrl(data), alt: data.alt ?? '' } })];
    } catch (error) {
      return [h('div', { className: 'error', text: error instanceof Error ? error.message : String(error) })];
    }
  }
}
