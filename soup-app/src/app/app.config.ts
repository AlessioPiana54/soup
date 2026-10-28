import { provideHttpClient } from '@angular/common/http';
import { APP_INITIALIZER, ApplicationConfig, provideZoneChangeDetection } from '@angular/core';
import { provideAnimationsAsync } from '@angular/platform-browser/animations/async';
import { provideRouter } from '@angular/router';

import { routes } from './app.routes';
import { PackageLoaderService } from './core/v3/package-loader.service';

// Application provider configuration
export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideRouter(routes),
    provideAnimationsAsync(),
    provideHttpClient(),
    // Load the frontend bundles of the active packages, without delaying the start
    {
      provide: APP_INITIALIZER,
      multi: true,
      deps: [PackageLoaderService],
      useFactory: (loader: PackageLoaderService) => () => {
        void loader.reload();
      }
    }
  ]
};
