import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

import { PlatformApiService } from '@cvm/platform-api-client';

@Component({
  selector: 'app-evals-page',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel">
      <h2>评估任务</h2>
      <p>触发本地 blocking suite，并查看本次评估结果。</p>
      <button (click)="run()">开始评估</button>
      <pre>{{ result | json }}</pre>
    </section>
  `,
  styles: [`
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    button { border: 0; border-radius: 999px; padding: 10px 16px; background: #112033; color: #fff; cursor: pointer; }
    pre { margin-top: 16px; overflow: auto; white-space: pre-wrap; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; }
  `]
})
export class EvalsPageComponent {
  result: any = null;

  constructor(private readonly api: PlatformApiService) {}

  async run(): Promise<void> {
    this.result = await this.api.createEvalRun();
  }
}
