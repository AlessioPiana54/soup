import { TestBed } from '@angular/core/testing';
import { firstValueFrom, Observable, of, throwError } from 'rxjs';

import { ONBOARDING_PREFERENCE, OnboardingService } from './onboarding.service';
import { V3ApiService } from './v3-api.service';

describe('OnboardingService', () => {
  let stored: Map<string, unknown>;
  let failGet: boolean;
  let service: OnboardingService;

  beforeEach(() => {
    stored = new Map();
    failGet = false;
    const api: Partial<V3ApiService> = {
      preference: <T>(key: string): Observable<T | null> =>
        failGet ? throwError(() => ({ statusCode: 503 })) : of((stored.get(key) ?? null) as T | null),
      setPreference: <T>(key: string, value: T): Observable<T> => {
        stored.set(key, value);
        return of(value);
      }
    };
    TestBed.configureTestingModule({ providers: [{ provide: V3ApiService, useValue: api }] });
    service = TestBed.inject(OnboardingService);
  });

  it('is the first time once, then records it', async () => {
    expect(await firstValueFrom(service.firstTime())).toBe(true);
    expect(stored.get(ONBOARDING_PREFERENCE)).toBe(false);
    expect(await firstValueFrom(service.firstTime())).toBe(false);
  });

  it('treats an explicit true as the first time', async () => {
    stored.set(ONBOARDING_PREFERENCE, true);
    expect(await firstValueFrom(service.firstTime())).toBe(true);
  });

  it('shows nothing without the preferences tool', async () => {
    failGet = true;
    expect(await firstValueFrom(service.firstTime())).toBe(false);
    expect(stored.size).toBe(0);
  });
});
