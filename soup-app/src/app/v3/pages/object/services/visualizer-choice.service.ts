import { Injectable } from '@angular/core';
import { catchError, forkJoin, map, Observable, of } from 'rxjs';

import { ObjectRef, VisualizerInfo } from '../../../../core/v3/v3.models';
import { V3ApiService } from '../../../../core/v3/v3-api.service';

/** The preference remembering the visualizer chosen for a kind. */
function visualizerPreferenceKey(kind: string): string {
  return `visualizer.${kind}`;
}

interface VisualizerChoice {
  visualizers: VisualizerInfo[];
  chosen: string | null;
}

/**
 * The visualizers of an object and the one to show, as in ProM: the one
 * chosen last time for the object's kind (the "visualizer.<kind>"
 * preference), else the first. An error lists none.
 */
@Injectable({
  providedIn: 'root'
})
export class VisualizerChoiceService {
  /**
   * Constructor for VisualizerChoiceService service
   * @param api the V3ApiService service
   */
  constructor(private api: V3ApiService) {}

  public load(object: ObjectRef): Observable<VisualizerChoice> {
    return forkJoin({
      visualizers: this.api.visualizers(object.id),
      preferred: this.api.preference<string>(visualizerPreferenceKey(object.kind)).pipe(catchError(() => of(null)))
    }).pipe(
      map(({ visualizers, preferred }) => {
        const chosen = visualizers.find((item) => item.id === preferred) ?? visualizers[0];
        return { visualizers, chosen: chosen?.id ?? null };
      }),
      catchError(() => of({ visualizers: [], chosen: null }))
    );
  }

  /** Remember `visualizerId` for the objects of `kind` (best effort). */
  public remember(kind: string, visualizerId: string): void {
    this.api.setPreference(visualizerPreferenceKey(kind), visualizerId).subscribe({ error: () => undefined });
  }
}
