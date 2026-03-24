import { Routes } from '@angular/router';

import { AgentsPageComponent } from './features/agents/agents.page';
import { CasesPageComponent } from './features/cases/cases.page';
import { EvalsPageComponent } from './features/evals/evals.page';
import { OpsPageComponent } from './features/ops/ops.page';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'cases' },
  { path: 'cases', component: CasesPageComponent },
  { path: 'agents', component: AgentsPageComponent },
  { path: 'ops', component: OpsPageComponent },
  { path: 'evals', component: EvalsPageComponent }
];
