import { Component, signal, ViewChild } from '@angular/core';
import { Router, RouterLink } from '@angular/router';
import { Block, columnsOf, FormValues } from '@soup/sdk';
import { NgxDropzoneModule } from 'ngx-dropzone';

import { ImporterInfo, Inspection } from '../../../core/v3/v3.models';
import { V3ApiService } from '../../../core/v3/v3-api.service';
import { NotificationService } from '../../../shared/components/s-toast/toast.service';
import { BlocksPreviewComponent } from '../../components/blocks-preview.component';
import { ConfigElementHostComponent } from '../../components/config-element-host.component';
import { DynamicFormComponent } from '../../components/dynamic-form.component';
import { errorMessage, notify } from '../../components/notify';

/**
 * /import - file -> the importers able to read it (several may: the user
 * picks one) -> inspect (preview and form, or the importer's own
 * configuration element) -> "Aggiorna anteprima" -> name and description
 * -> import -> the page of the new object. Preview blocks are drawn by a
 * visualizer of "report" (soup_base's <soup-report-view>); without one,
 * as JSON.
 */
@Component({
  selector: 'app-import',
  standalone: true,
  imports: [RouterLink, NgxDropzoneModule, DynamicFormComponent, ConfigElementHostComponent, BlocksPreviewComponent],
  templateUrl: './import.component.html',
  styleUrl: './import.component.scss'
})
export class ImportComponent {
  public readonly file = signal<File | null>(null);
  public readonly importers = signal<ImporterInfo[] | null>(null);
  public readonly importer = signal<ImporterInfo | null>(null);
  public readonly inspection = signal<Inspection | null>(null);
  public readonly columns = signal<string[]>([]);
  public readonly blocks = signal<Block[]>([]);
  public readonly options = signal<FormValues>({});

  public readonly name = signal('');
  public readonly description = signal('');
  public readonly nameTaken = signal(false);

  public readonly busy = signal('');
  public readonly error = signal('');

  @ViewChild(DynamicFormComponent)
  private form?: DynamicFormComponent;

  /**
   * Constructor for ImportComponent component
   * @param api the V3ApiService service
   * @param router the Router
   * @param notifications the NotificationService service
   */
  constructor(
    private api: V3ApiService,
    private router: Router,
    private notifications: NotificationService
  ) {}

  // --- 1. file ------------------------------------------------------------- //
  public onSelectFile(event: { addedFiles: File[] }): void {
    const [chosen] = event.addedFiles ?? [];
    if (!chosen || event.addedFiles.length !== 1) {
      notify(this.notifications, 'Scegli un solo file', 'error');
      return;
    }
    this.reset();
    this.file.set(chosen);
    this.name.set(chosen.name.replace(/\.[^.]+$/, ''));
    this.run('Ricerca degli importer...', () =>
      this.api.importers(chosen.name).subscribe({
        next: (importers) => {
          this.importers.set(importers);
          this.done();
          if (importers.length === 1) {
            this.chooseImporter(importers[0]);
          }
        },
        error: (error) => this.fail(error)
      })
    );
  }

  public removeFile(): void {
    this.reset();
  }

  // --- 2. importer --------------------------------------------------------- //
  public chooseImporter(importer: ImporterInfo): void {
    const file = this.file();
    if (!file) {
      return;
    }
    this.importer.set(importer);
    this.inspection.set(null);
    this.options.set({});
    this.run(`Analisi di ${file.name}...`, () =>
      this.api.inspect(importer.id, file).subscribe({
        next: (inspection) => {
          this.inspection.set(inspection);
          this.columns.set(columnsOf(inspection.preview));
          this.blocks.set(inspection.preview);
          this.done();
        },
        error: (error) => this.fail(error)
      })
    );
  }

  public changeImporter(): void {
    this.importer.set(null);
    this.inspection.set(null);
    this.blocks.set([]);
    this.error.set('');
  }

  // --- 3. options and preview ---------------------------------------------- //
  public onOptions(options: FormValues): void {
    this.options.set(options);
  }

  public refreshPreview(): void {
    const file = this.file();
    const importer = this.importer();
    if (!file || !importer || (this.form && !this.form.validate())) {
      return;
    }
    this.run('Aggiornamento anteprima...', () =>
      this.api.preview(importer.id, file, this.options()).subscribe({
        next: (blocks) => {
          if (blocks.length) {
            this.blocks.set(blocks);
          } else {
            notify(this.notifications, "L'importer non offre un'anteprima aggiornata", 'info');
          }
          this.done();
        },
        error: (error) => this.fail(error)
      })
    );
  }

  // --- 4. name and import -------------------------------------------------- //
  public onName(event: Event): void {
    this.name.set((event.target as HTMLInputElement).value);
    this.nameTaken.set(false);
  }

  public onDescription(event: Event): void {
    this.description.set((event.target as HTMLTextAreaElement).value);
  }

  public checkName(): void {
    const name = this.name().trim();
    if (name) {
      this.api.objectExists(name).subscribe({ next: (exists) => this.nameTaken.set(exists), error: () => this.nameTaken.set(false) });
    }
  }

  public importFile(): void {
    const file = this.file();
    const importer = this.importer();
    if (!file || !importer || (this.form && !this.form.validate())) {
      return;
    }
    if (!this.name().trim()) {
      this.error.set("Dai un nome all'oggetto");
      return;
    }
    this.run(`Import di ${file.name}...`, () =>
      this.api
        .import({ importerId: importer.id, file, name: this.name().trim(), description: this.description(), options: this.options() })
        .subscribe({
          next: (object) => {
            this.done();
            notify(this.notifications, `'${object.name}' importato`, 'success');
            void this.router.navigate(['/o', object.id]);
          },
          error: (error) => this.fail(error)
        })
    );
  }

  // --- helpers ------------------------------------------------------------- //
  private reset(): void {
    this.file.set(null);
    this.importers.set(null);
    this.importer.set(null);
    this.inspection.set(null);
    this.columns.set([]);
    this.blocks.set([]);
    this.options.set({});
    this.name.set('');
    this.description.set('');
    this.nameTaken.set(false);
    this.error.set('');
  }

  private run(message: string, start: () => void): void {
    this.busy.set(message);
    this.error.set('');
    start();
  }

  private done(): void {
    this.busy.set('');
  }

  private fail(error: unknown): void {
    this.busy.set('');
    this.error.set(errorMessage(error));
  }
}
