import { provideHttpClient } from '@angular/common/http';
import { ApplicationConfig, inject, provideAppInitializer, provideZoneChangeDetection } from '@angular/core';
import { provideRouter, withViewTransitions } from '@angular/router';

import { routes } from './app.routes';
import { PackageLoaderService } from './core/v3/package-loader.service';
import { PAGE_TRANSITIONS } from './page-transitions';

// Application provider configuration
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    // The pages slide at every change (page-transitions.ts, styles.scss)
    provideRouter(routes, withViewTransitions(PAGE_TRANSITIONS)),
    provideHttpClient(),
    // Load the frontend bundles of the active packages, without delaying the start
    provideAppInitializer(() => {
      void inject(PackageLoaderService).reload();
    })
  ]
};
