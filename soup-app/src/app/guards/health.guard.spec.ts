import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, UrlTree } from '@angular/router';
import { firstValueFrom, isObservable, Observable, of, throwError } from 'rxjs';

import { Health } from '../core/v3/v3.models';
import { V3ApiService } from '../core/v3/v3-api.service';
import { NotificationService } from '../shared/components/s-toast/toast.service';
import { engineGuard } from './health.guard';

describe('engineGuard', () => {
  let health: () => Observable<Health>;
  let toasts: string[];

  beforeEach(() => {
    toasts = [];
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        { provide: V3ApiService, useValue: { health: () => health() } },
        { provide: NotificationService, useValue: { showWithTitle: (title: string) => toasts.push(title) } }
      ]
    });
  });

  async function run(): Promise<boolean | UrlTree> {
    const result = TestBed.runInInjectionContext(() => engineGuard({} as never, {} as never));
    return isObservable(result) ? firstValueFrom(result as Observable<boolean | UrlTree>) : (result as boolean | UrlTree);
  }

  it('lets the page open when the Engine answers, even degraded', async () => {
    health = () => of({ status: 'degraded', tools: [], problems: ['memgraph: down'] });
    expect(await run()).toBe(true);
    expect(toasts).toEqual([]);
  });

  it('goes back to /welcome when the Engine does not answer', async () => {
    health = () => throwError(() => ({ statusCode: 0 }));
    const result = await run();
    expect(TestBed.inject(Router).serializeUrl(result as UrlTree)).toBe('/welcome');
    expect(toasts).toEqual(['Engine Off']);
  });
});
