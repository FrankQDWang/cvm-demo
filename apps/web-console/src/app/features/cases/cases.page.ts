import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { type ConditionPlanDraft, Verdict } from '@cvm/api-client-generated';

import { PlatformApiService } from '../../platform-api.service';

@Component({
  selector: 'app-cases-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="grid">
      <article class="panel">
        <h2>Case Workbench</h2>
        <p class="hint">顺序就是主流程：创建 Case，冻结 JD，生成草案，确认方案，发起 Run。</p>

        <label>Case Title</label>
        <input [(ngModel)]="title" placeholder="AI Native Recruiter" />

        <label>Owner Team</label>
        <input [(ngModel)]="ownerTeamId" placeholder="team-cn" />

        <label>JD Text</label>
        <textarea [(ngModel)]="jdText" rows="8"></textarea>

        <div class="actions">
          <button (click)="bootstrapFlow()">Run Full Flow</button>
          <button class="secondary" (click)="exportMasked()" [disabled]="!caseId">Export Masked</button>
        </div>

        <dl class="facts">
          <div><dt>Case</dt><dd>{{ caseId || '-' }}</dd></div>
          <div><dt>JD Version</dt><dd>{{ jdVersionId || '-' }}</dd></div>
          <div><dt>Plan</dt><dd>{{ planId || '-' }}</dd></div>
          <div><dt>Run</dt><dd>{{ runId || '-' }}</dd></div>
          <div><dt>Status</dt><dd>{{ runStatus || '-' }}</dd></div>
          <div><dt>Export</dt><dd>{{ exportStatus || '-' }}</dd></div>
        </dl>
      </article>

      <article class="panel">
        <h2>Draft & Snapshots</h2>
        <pre>{{ draft | json }}</pre>
        <div *ngIf="snapshots.length; else noSnapshots">
          <div class="snapshot" *ngFor="let snapshot of snapshots">
            <h3>Page {{ snapshot.pageNo }} · {{ snapshot.status }}</h3>
            <p>Total {{ snapshot.total }}</p>
            <button *ngFor="let candidate of snapshot.candidates" (click)="loadCandidate(candidate.candidateId)">
              {{ candidate.name }} · {{ candidate.title }} · {{ candidate.company }}
            </button>
          </div>
        </div>
        <ng-template #noSnapshots>
          <p class="hint">还没有页快照。</p>
        </ng-template>
      </article>
    </section>

    <section class="panel detail" *ngIf="selectedCandidate">
      <h2>Candidate Detail</h2>
      <p><strong>{{ selectedCandidate.candidate.name }}</strong> · {{ selectedCandidate.candidate.title }}</p>
      <p>{{ selectedCandidate.aiAnalysis.summary }}</p>
      <pre>{{ selectedCandidate.resumeSnapshot.content | json }}</pre>
      <div class="actions">
        <button (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.MATCH)">Match</button>
        <button class="secondary" (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.MAYBE)">Maybe</button>
        <button class="secondary" (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.NO)">No</button>
      </div>
      <pre>{{ verdictResponse | json }}</pre>
    </section>
  `,
  styles: [`
    .grid { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 20px; }
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    .detail { margin-top: 20px; }
    h2 { margin-top: 0; }
    label { display: block; margin: 14px 0 6px; font-size: 13px; text-transform: uppercase; letter-spacing: 0.08em; color: #475569; }
    input, textarea { width: 100%; border-radius: 16px; border: 1px solid rgba(17,32,51,0.12); padding: 12px 14px; background: #fff; }
    textarea { resize: vertical; }
    .actions { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
    button { border: 0; border-radius: 999px; padding: 10px 16px; background: #112033; color: #fff; cursor: pointer; }
    button.secondary { background: #dbe6f7; color: #112033; }
    button:disabled { opacity: 0.4; cursor: default; }
    .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .facts div { padding: 12px; border-radius: 16px; background: #f4f7fb; }
    dt { font-size: 12px; color: #64748b; }
    dd { margin: 4px 0 0; font-family: 'IBM Plex Mono', monospace; }
    .snapshot { padding: 12px; border-radius: 16px; background: #f8fafc; margin-bottom: 12px; }
    .snapshot button { display: block; width: 100%; margin-top: 8px; text-align: left; background: #fff; color: #112033; border: 1px solid rgba(17,32,51,0.08); }
    .hint { color: #475569; }
    pre { overflow: auto; white-space: pre-wrap; word-break: break-word; padding: 16px; border-radius: 16px; background: #0f172a; color: #dbeafe; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  `]
})
export class CasesPageComponent {
  readonly verdictEnum = Verdict;
  title = 'AI Native Recruiter';
  ownerTeamId = 'team-cn';
  jdText = 'Need Python FastAPI Angular Temporal candidate search experience with audit and export flows.';

  caseId = '';
  jdVersionId = '';
  planId = '';
  runId = '';
  runStatus = '';
  exportStatus = '';
  draft: ConditionPlanDraft | null = null;
  snapshots: Array<any> = [];
  selectedCandidate: any = null;
  verdictResponse: any = null;

  constructor(private readonly api: PlatformApiService) {}

  async bootstrapFlow(): Promise<void> {
    const caseResult = await this.api.createCase(this.title, this.ownerTeamId);
    this.caseId = caseResult.caseId;

    const version = await this.api.createJdVersion(this.caseId, this.jdText, 'manual');
    this.jdVersionId = version.jdVersionId;

    const draftJob = await this.api.createKeywordDraft(this.caseId, this.jdVersionId);
    this.planId = draftJob.planId;
    const draft = draftJob.draft as ConditionPlanDraft;
    this.draft = draft;

    const confirmed = await this.api.confirmPlan(this.planId, draft, 'consultant-web');
    this.planId = confirmed.planId;

    const run = await this.api.createSearchRun(this.caseId, this.planId);
    this.runId = run.runId;

    const status = await this.api.getSearchRun(this.runId);
    this.runStatus = status.status;

    const pages = await this.api.getSearchRunPages(this.runId);
    this.snapshots = pages.snapshots as Array<any>;
  }

  async loadCandidate(candidateId: string): Promise<void> {
    this.selectedCandidate = await this.api.getCandidate(candidateId);
  }

  async saveVerdict(candidateId: string, verdict: Verdict): Promise<void> {
    this.verdictResponse = await this.api.saveVerdict(candidateId, verdict);
  }

  async exportMasked(): Promise<void> {
    if (!this.caseId) {
      return;
    }
    const result = await this.api.createExport(this.caseId);
    this.exportStatus = result.status;
  }
}
