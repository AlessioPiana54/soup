import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { environment } from 'src/environments/environment';

import { V3ApiService } from '../core/v3/v3-api.service';
import { NotificationService } from '../shared/components/s-toast/toast.service';
import { ToastLevel } from '../shared/components/s-toast/toast_type.enum';

/**
 * The pages of the workspace need the SOUP Engine: GET /api/v3/health
 * answers when it is up (a tool that is down only makes the health
 * "degraded": the page opens and the welcome page shows which one). When
 * the Engine does not answer, a toast says so and the user goes back to
 * /welcome.
 */
export const engineGuard: CanActivateFn = () => {
  const api = inject(V3ApiService);
  const router = inject(Router);
  const toast = inject(NotificationService);
  return api.health().pipe(
    map(() => true),
    catchError(() => {
      toast.showWithTitle(
        'Engine Off',
        'The Engine is down. Please start the SOUP Engine',
        false,
        true,
        environment.prosLabUrl,
        ToastLevel.Warning,
        4000
      );
      return of(router.createUrlTree(['/welcome']));
    })
  );
};
