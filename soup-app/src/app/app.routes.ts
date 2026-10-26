import { Routes } from '@angular/router';

import { DatasetAuthGuard } from './guards/dataset_guard.guard';
import { EngineAuthGuard } from './guards/engine_guard.guard';
import { MemgraphAuthGuard } from './guards/memgraph_guard.guard';
import { WelcomeComponent } from './pages/welcome/welcome.component';

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
    path: 'new-dataset',
    loadComponent: () => import('./pages/new-dataset/new-dataset.component').then((c) => c.NewDatasetComponent),
    data: { animation: 'NewDatasetPage' },
    canActivate: [EngineAuthGuard, MemgraphAuthGuard]
  },
  {
    path: 'datasets',
    loadComponent: () => import('./pages/manage-datasets/manage-datasets.component').then((c) => c.ManageDatasetsComponent),
    data: { animation: 'DatasetsPage' },
    canActivate: [EngineAuthGuard, MemgraphAuthGuard]
  },
  {
    path: 'datasets/:name',
    loadComponent: () => import('./pages/details-dataset/details-dataset.component').then((c) => c.DetailsDatasetComponent),
    data: { animation: 'DetailsDatasetPage' },
    canActivate: [EngineAuthGuard, MemgraphAuthGuard, DatasetAuthGuard]
  },
  {
    path: 'datasets/:name/graph',
    loadComponent: () => import('./pages/graph-dataset/graph.component').then((c) => c.GraphComponent),
    data: { animatation: 'GraphDatasetPage' },
    canActivate: [EngineAuthGuard, MemgraphAuthGuard, DatasetAuthGuard]
  },
  {
    path: 'datasets/:name/:analysisName/graph',
    loadComponent: () => import('./pages/graph-dataset/graph.component').then((c) => c.GraphComponent),
    data: { animation: 'GraphDatasetPage' },
    canActivate: [EngineAuthGuard, MemgraphAuthGuard, DatasetAuthGuard]
  },
  // Pages of the /api/v3 workspace (the pages above stay until the v2 API is removed)
  {
    path: 'workspace',
    loadComponent: () => import('./v3/pages/workspace/workspace.component').then((c) => c.WorkspaceComponent),
    canActivate: [EngineAuthGuard]
  },
  {
    path: 'import',
    loadComponent: () => import('./v3/pages/import/import.component').then((c) => c.ImportComponent),
    canActivate: [EngineAuthGuard]
  },
  {
    path: 'o/:id',
    loadComponent: () => import('./v3/pages/object/object.component').then((c) => c.ObjectComponent),
    canActivate: [EngineAuthGuard]
  },
  {
    path: 'packages',
    loadComponent: () => import('./v3/pages/packages/packages.component').then((c) => c.PackagesComponent),
    canActivate: [EngineAuthGuard]
  },
  {
    path: '**',
    redirectTo: 'welcome'
  }
];
