import { DatePipe } from '@angular/common';
import { Component, computed, DestroyRef, OnInit, signal, ViewChild } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { download, FormValues } from '@soup/sdk';
import { forkJoin, of } from 'rxjs';
import { catchError } from 'rxjs/operators';

import { ExporterInfo, Field, ObjectRef, OperationInfo, VisualizerInfo, WorkspaceNode } from '../../../core/v3/v3.models';
import { V3ApiService } from '../../../core/v3/v3-api.service';
import { NotificationService } from '../../../shared/components/s-toast/toast.service';
import { DynamicFormComponent } from '../../components/dynamic-form.component';
import { errorMessage, notify } from '../../components/notify';
import { VisualizerHostComponent } from '../../components/visualizer-host.component';
import { findNode, flatten } from '../workspace/workspace-tree';

/** The preference remembering the visualizer chosen for a kind. */
export function visualizerPreferenceKey(kind: string): string {
  return `visualizer.${kind}`;
}

// The operation or exporter whose form is open
interface OpenForm<T> {
  item: T;
  fields: Field[];
  values: FormValues;
}

/**
 * /o/:id - one object: header and provenance (parents and derived
 * objects), the visualizer selector as in ProM (the first one is the
 * default, the choice is remembered per kind in the preferences), the
 * "Azioni" panel with the operations applicable to the object (their form,
 * then the new object's page) and the "Esporta" menu.
 */
@Component({
  selector: 'app-object',
  standalone: true,
  imports: [RouterLink, DatePipe, VisualizerHostComponent, DynamicFormComponent],
  templateUrl: './object.component.html',
  styleUrl: './object.component.scss'
})
export class ObjectComponent implements OnInit {
  public readonly object = signal<ObjectRef | null>(null);
  public readonly loadError = signal('');

  public readonly parents = signal<ObjectRef[]>([]);
  public readonly children = signal<ObjectRef[]>([]);

  public readonly visualizers = signal<VisualizerInfo[]>([]);
  public readonly visualizerId = signal<string | null>(null);
  public readonly visualizersLoaded = signal(false);
  public readonly visualizer = computed(() => this.visualizers().find((item) => item.id === this.visualizerId()) ?? null);

  public readonly operations = signal<OperationInfo[]>([]);
  public readonly groups = computed(() => {
    const groups = new Map<string, OperationInfo[]>();
    for (const operation of this.operations()) {
      const group = operation.group || 'Altro';
      groups.set(group, [...(groups.get(group) ?? []), operation]);
    }
    return Array.from(groups, ([name, items]) => ({ name, items }));
  });
  public readonly operationForm = signal<OpenForm<OperationInfo> | null>(null);

  public readonly exporters = signal<ExporterInfo[]>([]);
  public readonly exportForm = signal<OpenForm<ExporterInfo> | null>(null);
  public readonly exportOpen = signal(false);

  public readonly busy = signal('');
  public readonly actionError = signal('');

  @ViewChild('operationFields')
  private operationFields?: DynamicFormComponent;

  @ViewChild('exportFields')
  private exportFields?: DynamicFormComponent;

  /**
   * Constructor for ObjectComponent component
   * @param api the V3ApiService service
   * @param route the ActivatedRoute
   * @param router the Router
   * @param notifications the NotificationService service
   * @param destroyRef the DestroyRef
   */
  constructor(
    private api: V3ApiService,
    private route: ActivatedRoute,
    private router: Router,
    private notifications: NotificationService,
    private destroyRef: DestroyRef
  ) {}

  public ngOnInit(): void {
    // The same component shows the next object after an operation or a link.
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => this.load(params.get('id') ?? ''));
  }

  public load(id: string): void {
    this.object.set(null);
    this.loadError.set('');
    this.operationForm.set(null);
    this.exportForm.set(null);
    this.exportOpen.set(false);
    this.actionError.set('');

    this.api.object(id).subscribe({
      next: (object) => {
        this.object.set(object);
        this.loadVisualizers(object);
        this.loadProvenance(object);
        this.api.operations([object.id]).subscribe({ next: (items) => this.operations.set(items), error: () => this.operations.set([]) });
        this.api.exporters(object.id).subscribe({ next: (items) => this.exporters.set(items), error: () => this.exporters.set([]) });
      },
      error: (error) => this.loadError.set(errorMessage(error))
    });
  }

  // --- visualizers --------------------------------------------------------- //
  public chooseVisualizer(event: Event): void {
    const id = (event.target as HTMLSelectElement).value;
    const object = this.object();
    this.visualizerId.set(id);
    if (object) {
      this.api.setPreference(visualizerPreferenceKey(object.kind), id).subscribe({ error: () => undefined });
    }
  }

  private loadVisualizers(object: ObjectRef): void {
    this.visualizersLoaded.set(false);
    forkJoin({
      visualizers: this.api.visualizers(object.id),
      preferred: this.api.preference<string>(visualizerPreferenceKey(object.kind)).pipe(catchError(() => of(null)))
    }).subscribe({
      next: ({ visualizers, preferred }) => {
        this.visualizers.set(visualizers);
        const chosen = visualizers.find((item) => item.id === preferred) ?? visualizers[0];
        this.visualizerId.set(chosen?.id ?? null);
        this.visualizersLoaded.set(true);
      },
      error: () => {
        this.visualizers.set([]);
        this.visualizerId.set(null);
        this.visualizersLoaded.set(true);
      }
    });
  }

  private loadProvenance(object: ObjectRef): void {
    this.api.objects().subscribe({
      next: (nodes: WorkspaceNode[]) => {
        const all = flatten(nodes).map((node) => node.object);
        this.parents.set(object.parents.map((id) => all.find((item) => item.id === id)).filter((item): item is ObjectRef => !!item));
        const node = findNode(nodes, object.id);
        this.children.set(node ? node.children.map((child) => child.object) : []);
      },
      error: () => undefined
    });
  }

  // --- operations ---------------------------------------------------------- //
  public openOperation(operation: OperationInfo): void {
    const object = this.object();
    if (!object) {
      return;
    }
    this.actionError.set('');
    this.api.operationFields(operation.id, [object.id]).subscribe({
      next: (fields) => this.operationForm.set({ item: operation, fields, values: {} }),
      error: (error) => this.actionError.set(errorMessage(error))
    });
  }

  public onOperationValues(values: FormValues): void {
    const form = this.operationForm();
    if (form) {
      this.operationForm.set({ ...form, values });
    }
  }

  public closeOperation(): void {
    this.operationForm.set(null);
  }

  public runOperation(): void {
    const form = this.operationForm();
    const object = this.object();
    if (!form || !object || (this.operationFields && !this.operationFields.validate())) {
      return;
    }
    this.busy.set(`${form.item.label}...`);
    this.actionError.set('');
    this.api.runOperation(form.item.id, [object.id], form.values).subscribe({
      next: (created) => {
        this.busy.set('');
        notify(this.notifications, `${form.item.label}: ${created.length} oggetto/i creati`, 'success');
        if (created.length) {
          void this.router.navigate(['/o', created[0].id]);
        }
      },
      error: (error) => {
        this.busy.set('');
        this.actionError.set(errorMessage(error));
      }
    });
  }

  // --- export -------------------------------------------------------------- //
  public toggleExport(): void {
    this.exportOpen.update((open) => !open);
  }

  public chooseExporter(exporter: ExporterInfo): void {
    this.exportOpen.set(false);
    if (exporter.fields.length) {
      this.exportForm.set({ item: exporter, fields: exporter.fields, values: {} });
    } else {
      this.export(exporter, {});
    }
  }

  public onExportValues(values: FormValues): void {
    const form = this.exportForm();
    if (form) {
      this.exportForm.set({ ...form, values });
    }
  }

  public confirmExport(): void {
    const form = this.exportForm();
    if (form && (!this.exportFields || this.exportFields.validate())) {
      this.export(form.item, form.values);
    }
  }

  public closeExport(): void {
    this.exportForm.set(null);
  }

  private export(exporter: ExporterInfo, values: FormValues): void {
    const object = this.object();
    if (!object) {
      return;
    }
    this.busy.set(`Esportazione ${exporter.label}...`);
    this.api.export(object.id, exporter, values).subscribe({
      next: (file) => {
        this.busy.set('');
        this.exportForm.set(null);
        download(file.filename, exporter.mime, file.blob);
      },
      error: (error) => {
        this.busy.set('');
        this.actionError.set(errorMessage(error));
      }
    });
  }
}
