import { Injectable } from '@angular/core';
import { catchError, map, Observable, of, switchMap } from 'rxjs';

import { V3ApiService } from './v3-api.service';

/** The preference (tool "preferences") that replaces the OnBoarding node of Memgraph. */
export const ONBOARDING_PREFERENCE = 'onboarding.first_time';

/**
 * The first-access hint: shown once, the first time an object is opened.
 * Unset (or true) means it was never shown; it becomes false as soon as it
 * is. Without the preferences tool the hint is not shown.
 */
@Injectable({
  providedIn: 'root'
})
export class OnboardingService {
  /**
   * Constructor for OnboardingService service
   * @param api the V3ApiService service
   */
  constructor(private api: V3ApiService) {}

  /** Emits true once, the first time ever (and records that the hint was shown). */
  public firstTime(): Observable<boolean> {
    return this.api.preference<boolean>(ONBOARDING_PREFERENCE).pipe(
      switchMap((value) =>
        value === false
          ? of(false)
          : this.api.setPreference(ONBOARDING_PREFERENCE, false).pipe(
              map(() => true),
              // Not recorded: better not to show it again at every opening.
              catchError(() => of(false))
            )
      ),
      catchError(() => of(false))
    );
  }
}
