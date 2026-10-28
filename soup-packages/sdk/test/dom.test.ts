import { describe, expect, it, vi } from 'vitest';

import { errorMessage, h } from '../src/dom';

describe('h()', () => {
  it('builds an element with class, text, attributes, listeners and children', () => {
    const click = vi.fn();
    const element = h(
      'button',
      { className: 'go', text: 'Vai', attrs: { type: 'button', 'data-x': '1' }, on: { click } },
      null,
      undefined
    );

    element.click();
    expect(element.className).toBe('go');
    expect(element.textContent).toBe('Vai');
    expect(element.getAttribute('type')).toBe('button');
    expect(element.dataset['x']).toBe('1');
    expect(click).toHaveBeenCalledOnce();
  });

  it('appends nodes and strings in order, skipping null and undefined', () => {
    const element = h('p', {}, 'a', null, h('b', { text: 'b' }), undefined, 'c');

    expect(element.childNodes).toHaveLength(3);
    expect(element.textContent).toBe('abc');
  });

  it('never parses text as markup', () => {
    const element = h('div', { text: '<img src=x onerror=alert(1)>' }, '<script>x</script>');

    expect(element.querySelector('img')).toBeNull();
    expect(element.querySelector('script')).toBeNull();
    expect(element.textContent).toBe('<img src=x onerror=alert(1)><script>x</script>');
  });

  it('leaves the class empty for an empty className and sets an empty text', () => {
    const element = h('span', { className: '', text: '' }, 'kept');

    expect(element.hasAttribute('class')).toBe(false);
    expect(element.textContent).toBe('kept');
  });
});

describe('errorMessage()', () => {
  it('gives the message of an Error and the text of anything else', () => {
    expect(errorMessage(new Error('boom'))).toBe('boom');
    expect(errorMessage('plain')).toBe('plain');
    expect(errorMessage(42)).toBe('42');
  });
});
