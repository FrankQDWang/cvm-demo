import { Routes } from '@angular/router';

import { EvalsPageComponent } from './features/evals/evals.page';

export const routes: Routes = [
  { path: '', component: EvalsPageComponent },
  { path: '**', redirectTo: '' }
];
