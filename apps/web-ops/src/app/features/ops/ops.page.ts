import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  type OpsSummaryResponse,
  PlatformApiService,
  type TemporalAgentRunDiagnosticResponse,
} from '@cvm/platform-api-client';

@Component({
  selector: 'app-ops-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="layout">
      <section class="panel">
        <div class="row">
          <div>
            <h2>运行总览</h2>
            <p>查看批次队列、失败分类、延迟、版本和 visibility 后端。</p>
          </div>
          <button (click)="reload()">刷新</button>
        </div>
        <div class="summary-grid" *ngIf="summary?.version as version">
          <article class="card">
            <span>API Build</span>
            <strong>{{ version.apiBuildId || '-' }}</strong>
          </article>
          <article class="card">
            <span>Worker Build</span>
            <strong>{{ version.workerBuildId || '-' }}</strong>
          </article>
          <article class="card">
            <span>Visibility</span>
            <strong>{{ version.temporalVisibilityBackend || '-' }}</strong>
          </article>
          <article class="card">
            <span>Namespace</span>
            <strong>{{ version.temporalNamespace || '-' }}</strong>
          </article>
        </div>
        <pre>{{ summary | json }}</pre>
      </section>

      <section class="panel diagnostics">
        <div class="row">
          <div>
            <h2>Temporal Diagnostics</h2>
            <p>输入 <code>agentRunId</code>，查看应用状态、execution 状态、visibility 索引和 Langfuse trace。</p>
          </div>
        </div>
        <label class="field">
          <span>Agent Run ID</span>
          <div class="input-row">
            <input [(ngModel)]="runId" placeholder="agent_xxx" />
            <button (click)="inspect()" [disabled]="!runId.trim() || loadingDiagnostic">
              {{ loadingDiagnostic ? '查询中...' : '查询' }}
            </button>
          </div>
        </label>
        <p class="error" *ngIf="diagnosticError">{{ diagnosticError }}</p>
        <ng-container *ngIf="diagnostic as item">
          <div class="summary-grid">
            <article class="card">
              <span>App Status</span>
              <strong>{{ item.appStatus }}</strong>
            </article>
            <article class="card">
              <span>Current Round</span>
              <strong>{{ item.currentRound }}</strong>
            </article>
            <article class="card">
              <span>Step Count</span>
              <strong>{{ item.stepCount }}</strong>
            </article>
            <article class="card">
              <span>Final Shortlist</span>
              <strong>{{ item.finalShortlistCount }}</strong>
            </article>
            <article class="card">
              <span>Execution Found</span>
              <strong>{{ item.temporalExecutionFound ? 'true' : 'false' }}</strong>
            </article>
            <article class="card">
              <span>Execution Status</span>
              <strong>{{ item.temporalExecutionStatus || '-' }}</strong>
            </article>
            <article class="card">
              <span>Visibility Indexed</span>
              <strong>{{ item.visibilityIndexed ? 'true' : 'false' }}</strong>
            </article>
            <article class="card">
              <span>Workflow ID</span>
              <strong>{{ item.workflowId }}</strong>
            </article>
            <article class="card">
              <span>Task Queue</span>
              <strong>{{ item.taskQueue }}</strong>
            </article>
          </div>
          <p *ngIf="item.stopReason" class="error">Stop: {{ item.stopReason }}</p>
          <p *ngIf="item.error" class="error">{{ item.error }}</p>
          <a
            *ngIf="item.temporalUiUrl"
            [href]="item.temporalUiUrl"
            target="_blank"
            rel="noreferrer"
            class="link"
          >
            打开 Temporal UI
          </a>
          <a
            *ngIf="item.langfuseTraceUrl"
            [href]="item.langfuseTraceUrl"
            target="_blank"
            rel="noreferrer"
            class="link"
          >
            打开 Langfuse Trace
          </a>
          <pre>{{ item | json }}</pre>
        </ng-container>
      </section>
    </section>
  `,
  styles: [`
    .layout { display: grid; gap: 20px; }
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    .row { display: flex; justify-content: space-between; gap: 16px; align-items: center; }
    .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }
    .card { padding: 14px 16px; border-radius: 18px; background: #f8fafc; border: 1px solid rgba(17,32,51,0.08); display: grid; gap: 6px; }
    .card span { color: #475569; font-size: 13px; }
    .card strong { color: #0f172a; font-size: 15px; }
    .field { display: grid; gap: 8px; margin-top: 16px; }
    .field span { font-size: 13px; color: #334155; }
    .input-row { display: flex; gap: 12px; }
    input { flex: 1; border: 1px solid rgba(17,32,51,0.16); border-radius: 999px; padding: 12px 16px; font: inherit; }
    button { border: 0; border-radius: 999px; padding: 10px 16px; background: #112033; color: #fff; cursor: pointer; }
    button[disabled] { opacity: 0.6; cursor: wait; }
    .link { display: inline-flex; margin-top: 16px; color: #1d4ed8; font-weight: 600; }
    .error { margin-top: 12px; color: #b91c1c; }
    pre { margin-top: 16px; overflow: auto; white-space: pre-wrap; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; }
  `]
})
export class OpsPageComponent implements OnInit {
  summary: OpsSummaryResponse | null = null;
  runId = '';
  diagnostic: TemporalAgentRunDiagnosticResponse | null = null;
  diagnosticError = '';
  loadingDiagnostic = false;

  constructor(private readonly api: PlatformApiService) {}

  ngOnInit(): void {
    void this.reload();
  }

  async reload(): Promise<void> {
    this.summary = await this.api.getOpsSummary();
  }

  async inspect(): Promise<void> {
    if (!this.runId.trim()) {
      return;
    }
    this.loadingDiagnostic = true;
    this.diagnosticError = '';
    try {
      this.diagnostic = await this.api.getAgentRunTemporalDiagnostic(this.runId.trim());
    } catch (error) {
      this.diagnostic = null;
      this.diagnosticError = error instanceof Error ? error.message : '查询失败';
    } finally {
      this.loadingDiagnostic = false;
    }
  }
}
