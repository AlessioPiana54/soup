import { describe, expect, it } from 'vitest';

import {
  ActionContext,
  createVisualizerContext,
  DownloadContext,
  NavigationContext,
  NotifyContext,
  ObjectContext,
  SOUP_EVENTS,
  ThumbnailContext,
  VisualizerContext
} from '../src';

const OBJECT = {
  id: 'o1',
  name: 'orders',
  kind: 'table',
  created_by: { type: 'importer' as const, contributor_id: 'x.y', package: 'x' },
  parents: [],
  created_at: '',
  description: '',
  meta: {}
};

/** A helper that needs only the notifications: it accepts any VisualizerContext. */
function warn(context: NotifyContext, message: string): void {
  context.notify(message, 'warning');
}

describe('VisualizerContext', () => {
  it('is made of one part per capability, each usable on its own', () => {
    const target = new EventTarget();
    const seen: string[] = [];
    target.addEventListener(SOUP_EVENTS.notify, (event) => seen.push((event as CustomEvent).detail.message));
    const context: VisualizerContext = createVisualizerContext(target, { object: OBJECT, action: async () => ({ ok: true }) });

    const parts: [ObjectContext, ActionContext, NavigationContext, NotifyContext, ThumbnailContext, DownloadContext] = [
      context,
      context,
      context,
      context,
      context,
      context
    ];
    warn(context, 'careful');

    expect(parts.every((part) => part === context)).toBe(true);
    expect(context.object.id).toBe('o1');
    expect(seen).toEqual(['careful']);
  });
});
