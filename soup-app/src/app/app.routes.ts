import { Routes } from '@angular/router';

import { engineGuard } from './guards/health.guard';
import { WelcomeComponent } from './pages/welcome/welcome.component';
import { legacyObjectRedirect } from './v3/legacy-redirects';

// The redirects only run their guard: the component is never shown.
const redirectOnly = () => import('./pages/welcome/welcome.component').then((c) => c.WelcomeComponent);

// Application routes
export const routes: Routes = [
  {
    path: '',
    pathMatch: 'full',
    redirectTo: 'welcome'
  },
  {
    path: 'welcome',
    component: WelcomeComponent
  },
  {
    path: 'workspace',
    loadComponent: () => import('./v3/pages/workspace/workspace.component').then((c) => c.WorkspaceComponent),
    canActivate: [engineGuard]
  },
  {
    path: 'import',
    loadComponent: () => import('./v3/pages/import/import.component').then((c) => c.ImportComponent),
    canActivate: [engineGuard]
  },
  {
    path: 'o/:id',
    loadComponent: () => import('./v3/pages/object/object.component').then((c) => c.ObjectComponent),
    canActivate: [engineGuard]
  },
  {
    path: 'packages',
    loadComponent: () => import('./v3/pages/packages/packages.component').then((c) => c.PackagesComponent),
    canActivate: [engineGuard]
  },
  // The addresses of the old pages
  {
    path: 'new-dataset',
    redirectTo: 'import'
  },
  {
    path: 'datasets',
    pathMatch: 'full',
    redirectTo: 'workspace'
  },
  {
    path: 'datasets/:name',
    loadComponent: redirectOnly,
    canActivate: [engineGuard, legacyObjectRedirect]
  },
  {
    path: 'datasets/:name/graph',
    loadComponent: redirectOnly,
    canActivate: [engineGuard, legacyObjectRedirect]
  },
  {
    path: 'datasets/:name/:analysisName/graph',
    loadComponent: redirectOnly,
    canActivate: [engineGuard, legacyObjectRedirect]
  },
  {
    path: '**',
    redirectTo: 'welcome'
  }
];
