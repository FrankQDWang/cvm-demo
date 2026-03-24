import { Routes } from '@angular/router';

import { CasesPageComponent } from './features/cases/cases.page';

export const routes: Routes = [
  { path: '', component: CasesPageComponent },
  { path: '**', redirectTo: '' }
];
