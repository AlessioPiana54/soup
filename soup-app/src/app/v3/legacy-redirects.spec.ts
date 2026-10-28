import { ObjectRef } from '@soup/sdk';

import { WorkspaceNode } from '../core/v3/v3.models';
import { resolveLegacy } from './legacy-redirects';

function node(id: string, name: string, meta: Record<string, unknown> = {}, children: WorkspaceNode[] = []): WorkspaceNode {
  const object = { id, name, kind: 'ekg', description: '', parents: [], meta } as unknown as ObjectRef;
  return { object, package: 'csv_ekg', package_status: 'active', package_missing: false, children };
}

describe('resolveLegacy', () => {
  const nested = node('a2', 'deeper', { analysis: { dataset: 'orders', name: 'deeper' } });
  const analysis = node('a1', 'renamed', { analysis: { dataset: 'orders', name: 'first' } }, [nested]);
  const roots = [node('d1', 'orders', { dataset: 'orders' }, [analysis]), node('d2', 'Renamed dataset', { dataset: 'legacy_name' })];

  it('finds a dataset by name or by its adopted folder', () => {
    expect(resolveLegacy(roots, 'orders')?.id).toBe('d1');
    expect(resolveLegacy(roots, 'legacy_name')?.id).toBe('d2');
  });

  it('finds an analysis of the dataset by its file name, also nested', () => {
    expect(resolveLegacy(roots, 'orders', 'first')?.id).toBe('a1');
    expect(resolveLegacy(roots, 'orders', 'deeper')?.id).toBe('a2');
    expect(resolveLegacy(roots, 'orders', 'renamed')?.id).toBe('a1');
  });

  it('answers null for an unknown name', () => {
    expect(resolveLegacy(roots, 'nope')).toBeNull();
    expect(resolveLegacy(roots, 'orders', 'nope')).toBeNull();
    expect(resolveLegacy(roots, 'legacy_name', 'first')).toBeNull();
  });
});
