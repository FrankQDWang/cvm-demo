import { Component } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  readonly navItems = [
    { path: '/cases', label: 'Cases' },
    { path: '/agents', label: 'Agents' },
    { path: '/ops', label: 'Ops' },
    { path: '/evals', label: 'Evals' }
  ];
}
