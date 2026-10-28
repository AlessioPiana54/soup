import { GraphModel } from './model';

/** The colors of the old GraphComponent (predefinedColors), in order of appearance. */
export const PREDEFINED_COLORS: readonly string[] = [
  '#3f51b5',
  '#ff5722',
  '#4caf50',
  '#e91e63',
  '#ffc107',
  '#795548',
  '#00bcd4',
  '#9c27b0',
  '#8bc34a',
  '#2196f3',
  '#ff9800',
  '#607d8b',
  '#009688',
  '#f44336',
  '#673ab7'
];

interface PaletteEntry {
  name: string;
  color: string;
  visible: boolean;
}

class ColorMap {
  private readonly colors = new Map<string, string>();
  private readonly hidden = new Set<string>();

  public add(name: string): void {
    if (!this.colors.has(name)) this.colors.set(name, PREDEFINED_COLORS[this.colors.size % PREDEFINED_COLORS.length]);
  }

  public color(name: string): string {
    return this.colors.get(name) ?? PREDEFINED_COLORS[0];
  }

  public isVisible(name: string): boolean {
    return !this.hidden.has(name);
  }

  public setVisible(name: string, visible: boolean): void {
    if (visible) this.hidden.delete(name);
    else this.hidden.add(name);
  }

  public entries(): PaletteEntry[] {
    return [...this.colors].map(([name, color]) => ({ name, color, visible: this.isVisible(name) }));
  }

  public clear(): void {
    this.colors.clear();
    this.hidden.clear();
  }
}

/**
 * RelationshipPalette - colors and visibility per relationship type and
 * per node group, separate from the engine that draws them. assign()
 * adds the types/groups of a model and keeps the ones already known, so
 * colors and hidden types survive a redraw or new data (the old page
 * cleared the colors at every injectData and pushed the relationships
 * again, listing them twice).
 */
export class RelationshipPalette {
  private readonly relationships = new ColorMap();
  private readonly groups = new ColorMap();

  public assign(model: GraphModel): void {
    for (const edge of model.edges) this.relationships.add(edge.type);
    for (const node of model.nodes) if (node.group) this.groups.add(node.group);
  }

  public colorOf(type: string): string {
    return this.relationships.color(type);
  }

  public isVisible(type: string): boolean {
    return this.relationships.isVisible(type);
  }

  public setVisible(type: string, visible: boolean): void {
    this.relationships.setVisible(type, visible);
  }

  public relationshipTypes(): PaletteEntry[] {
    return this.relationships.entries();
  }

  public groupColorOf(group: string): string {
    return this.groups.color(group);
  }

  public isGroupVisible(group: string): boolean {
    return !group || this.groups.isVisible(group);
  }

  public setGroupVisible(group: string, visible: boolean): void {
    this.groups.setVisible(group, visible);
  }

  public nodeGroups(): PaletteEntry[] {
    return this.groups.entries();
  }

  public reset(): void {
    this.relationships.clear();
    this.groups.clear();
  }
}
