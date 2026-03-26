import { Routes } from '@angular/router';

import { ShortlistPageComponent } from './features/shortlist/shortlist.page';

export const routes: Routes = [
  { path: '', component: ShortlistPageComponent },
  { path: '**', redirectTo: '' }
];
