import { Routes } from '@angular/router';

import { OpsPageComponent } from './features/ops/ops.page';

export const routes: Routes = [
  { path: '', component: OpsPageComponent },
  { path: '**', redirectTo: '' }
];
