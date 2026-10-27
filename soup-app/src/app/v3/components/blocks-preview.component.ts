import { Component, computed, effect, input, signal, untracked } from '@angular/core';
import { Block, ObjectRef, REPORT_KIND, ReportData } from '@soup/sdk';

import { PackageLoaderService } from '../../core/v3/package-loader.service';
import { VisualizerInfo } from '../../core/v3/v3.models';
import { V3ApiService } from '../../core/v3/v3-api.service';
import { VisualizerHostComponent } from './visualizer-host.component';

/**
 * <soup-blocks-preview [blocks]> - blocks that are not an object yet (the
 * preview of an import), drawn by the first visualizer installed for the
 * "report" kind with the same data a report object would give it
 * ({blocks}). Without one, the visualizer host says that none is
 * installed for "report" and shows the blocks as JSON. The visualizers
 * are looked up again when the frontend packages change.
 */
@Component({
  selector: 'soup-blocks-preview',
  standalone: true,
  imports: [VisualizerHostComponent],
  template: `
    @if (this.ready()) {
      <soup-visualizer-host
        [object]="this.object()"
        [visualizer]="this.visualizer()"
        [data]="this.data()"></soup-visualizer-host>
    }
  `
})
export class BlocksPreviewComponent {
  // The blocks to draw
  public blocks = input.required<readonly Block[]>();

  // The name shown by visualizers that show one
  public name = input<string>('');

  public readonly visualizer = signal<VisualizerInfo | null>(null);
  public readonly ready = signal(false);

  // Stable references: the host remounts its element when an input changes.
  public readonly data = computed<ReportData>(() => ({ blocks: [...this.blocks()], name: this.name() }));
  public readonly object = computed<ObjectRef>(() => ({
    id: '',
    name: this.name(),
    kind: REPORT_KIND,
    created_by: { type: 'importer', contributor_id: '', package: '' },
    parents: [],
    created_at: '',
    description: '',
    meta: { blocks: [...this.blocks()] }
  }));

  private request = 0;

  /**
   * Constructor for BlocksPreviewComponent component
   * @param api the V3ApiService service
   * @param loader the PackageLoaderService service (its statuses change after install/enable/disable)
   */
  constructor(
    private api: V3ApiService,
    loader: PackageLoaderService
  ) {
    effect(() => {
      loader.statuses();
      untracked(() => this.lookup());
    });
  }

  private lookup(): void {
    const request = ++this.request;
    this.api.visualizersForKind(REPORT_KIND).subscribe({
      next: (visualizers) => {
        if (request === this.request) {
          this.visualizer.set(visualizers[0] ?? null);
          this.ready.set(true);
        }
      },
      error: () => {
        if (request === this.request) {
          this.visualizer.set(null);
          this.ready.set(true);
        }
      }
    });
  }
}
