import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';

import { PlatformApiService } from '../../platform-api.service';

@Component({
  selector: 'app-ops-page',
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="panel">
      <div class="row">
        <div>
          <h2>Ops Summary</h2>
          <p>本地模式下最小可观测面：Search Run 队列、失败分类、版本指标。</p>
        </div>
        <button (click)="reload()">Refresh</button>
      </div>
      <pre>{{ summary | json }}</pre>
    </section>
  `,
  styles: [`
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    .row { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    button { border: 0; border-radius: 999px; padding: 10px 16px; background: #112033; color: #fff; cursor: pointer; }
    pre { margin-top: 16px; overflow: auto; white-space: pre-wrap; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; }
  `]
})
export class OpsPageComponent implements OnInit {
  summary: any = {};

  constructor(private readonly api: PlatformApiService) {}

  ngOnInit(): void {
    void this.reload();
  }

  async reload(): Promise<void> {
    this.summary = await this.api.getOpsSummary();
  }
}
