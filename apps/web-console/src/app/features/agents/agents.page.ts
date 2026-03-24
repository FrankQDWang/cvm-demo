import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

@Component({
  selector: 'app-agents-page',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel">
      <h2>Agent Governance</h2>
      <p>这个路由先承接治理入口，不做复杂控制台。</p>
      <ul>
        <li><code>AGENTS.md</code> 只做仓库地图。</li>
        <li><code>docs/EXEC-PLANS/active</code> 存放执行计划。</li>
        <li><code>contracts/</code> 是边界事实源，生成物禁止手改。</li>
        <li><code>contracts/external/cts.validated.yaml</code> 是真实 CTS contract 基线。</li>
      </ul>
    </section>
  `,
  styles: [`
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    ul { margin: 0; padding-left: 20px; }
    li { margin: 10px 0; }
  `]
})
export class AgentsPageComponent {}
