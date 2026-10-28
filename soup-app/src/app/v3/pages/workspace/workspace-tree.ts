import { WorkspaceNode } from '../../../core/v3/v3.models';

/**
 * The workspace tree (GET /api/v3/objects): every object under the
 * object(s) it was derived from. Pure functions for the filters and for
 * the provenance shown on an object's page.
 */

interface WorkspaceFilter {
  search: string;
  kind: string;
  package: string;
}

function matches(node: WorkspaceNode, filter: WorkspaceFilter): boolean {
  const search = filter.search.trim().toLowerCase();
  const object = node.object;
  return (
    (!filter.kind || object.kind === filter.kind) &&
    (!filter.package || node.package === filter.package) &&
    (!search || object.name.toLowerCase().includes(search) || object.description.toLowerCase().includes(search))
  );
}

/** The nodes matching the filter, with their ancestors (to keep the provenance visible). */
export function filterTree(nodes: readonly WorkspaceNode[], filter: WorkspaceFilter): WorkspaceNode[] {
  const result: WorkspaceNode[] = [];
  for (const node of nodes) {
    const children = filterTree(node.children, filter);
    if (children.length || matches(node, filter)) {
      result.push({ ...node, children });
    }
  }
  return result;
}

/** Every node, depth first (an object with two parents appears under both). */
export function flatten(nodes: readonly WorkspaceNode[]): WorkspaceNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)]);
}

export function distinct(values: Iterable<string>): string[] {
  return Array.from(new Set(values)).sort((a, b) => a.localeCompare(b));
}

export function findNode(nodes: readonly WorkspaceNode[], id: string): WorkspaceNode | undefined {
  return flatten(nodes).find((node) => node.object.id === id);
}

export function countDescendants(node: WorkspaceNode): number {
  return new Set(flatten(node.children).map((child) => child.object.id)).size;
}
