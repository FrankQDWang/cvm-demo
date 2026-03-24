import { CommonModule } from '@angular/common';
import { Component, OnDestroy } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  type CandidateDetailResponse,
  type ConditionPlanDraft,
  type SearchRunPageSnapshot,
  Verdict,
  PlatformApiService,
} from '@cvm/platform-api-client';

type ResumeRecord = Record<string, unknown>;

@Component({
  selector: 'app-cases-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="hero panel">
      <h2>岗位寻访流程</h2>
      <p class="hint">从岗位说明出发，生成筛选建议、浏览候选人、查看简历要点，并导出短名单。</p>
    </section>

    <section class="grid">
      <article class="panel">
        <div class="step-title"><span>1</span><h3>新建岗位需求</h3></div>

        <label>岗位名称</label>
        <input [(ngModel)]="title" placeholder="例如：在线教育算法工程师" />

        <label>负责团队</label>
        <input [(ngModel)]="ownerTeamId" placeholder="例如：team-beijing-edtech" />

        <label>岗位说明</label>
        <textarea [(ngModel)]="jdText" rows="12"></textarea>

        <div class="actions">
          <button (click)="createCaseAndJd()">保存岗位需求</button>
        </div>

        <dl class="facts">
          <div><dt>岗位编号</dt><dd>{{ caseId || '-' }}</dd></div>
          <div><dt>说明版本</dt><dd>{{ jdVersionId || '-' }}</dd></div>
          <div><dt>筛选方案</dt><dd>{{ planId || '-' }}</dd></div>
          <div><dt>寻访批次</dt><dd>{{ runId || '-' }}</dd></div>
          <div><dt>批次状态</dt><dd>{{ statusLabel(runStatus) }}</dd></div>
          <div><dt>导出状态</dt><dd>{{ exportStatusLabel() }}</dd></div>
        </dl>
      </article>

      <article class="panel">
        <div class="step-title"><span>2</span><h3>生成寻访建议</h3></div>
        <p class="hint">系统会先给出一版重点关键词和筛选建议，你可以继续调整后确认。</p>
        <div class="actions">
          <button (click)="generateDraft()" [disabled]="!jdVersionId">生成寻访建议</button>
        </div>

        <div *ngIf="draft; else noDraft">
          <label>重点关键词</label>
          <textarea [(ngModel)]="mustTermsText" rows="4"></textarea>

          <label>加分关键词</label>
          <textarea [(ngModel)]="shouldTermsText" rows="4"></textarea>

          <label>排除关键词</label>
          <textarea [(ngModel)]="excludeTermsText" rows="3"></textarea>

          <div class="filters-grid">
            <div>
              <label>意向城市</label>
              <input [(ngModel)]="locationText" placeholder="北京, 上海" />
            </div>
            <div>
              <label>学历要求</label>
              <input [(ngModel)]="degreeText" placeholder="例如：2" />
            </div>
            <div>
              <label>院校层级</label>
              <input [(ngModel)]="schoolTypeText" placeholder="例如：1" />
            </div>
            <div>
              <label>工作年限</label>
              <input [(ngModel)]="workExperienceRangeText" placeholder="例如：4" />
            </div>
            <div>
              <label>岗位方向</label>
              <input [(ngModel)]="positionText" placeholder="例如：工程师" />
            </div>
            <div>
              <label>经历方向</label>
              <input [(ngModel)]="workContentText" placeholder="例如：语音、大模型、推荐" />
            </div>
            <div>
              <label>目标公司</label>
              <input [(ngModel)]="companyText" placeholder="例如：字节跳动, 百度" />
            </div>
            <div>
              <label>目标院校</label>
              <input [(ngModel)]="schoolText" placeholder="例如：清华大学, 北京大学" />
            </div>
            <div>
              <label>每页人数</label>
              <input [(ngModel)]="pageSizeText" placeholder="10" />
            </div>
            <div>
              <label>拉取页数</label>
              <input [(ngModel)]="pageBudgetText" placeholder="1" />
            </div>
          </div>

          <div class="actions">
            <button (click)="confirmPlan()" [disabled]="!planId">确认筛选条件</button>
          </div>

          <dl class="facts compact-facts">
            <div *ngFor="let item of conditionSummaryItems()">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </div>
          </dl>
        </div>

        <ng-template #noDraft>
          <p class="hint">请先保存岗位需求，再生成一版建议。</p>
        </ng-template>
      </article>
    </section>

    <section class="grid">
      <article class="panel">
        <div class="step-title"><span>3</span><h3>开始寻访</h3></div>
        <p class="hint">确认当前筛选条件后，发起一批新的寻访。调整条件后可以再次发起，历史结果会保留。</p>
        <div class="actions">
          <button (click)="createSearchRun()" [disabled]="!planConfirmed">开始寻访</button>
          <button class="secondary" (click)="refreshRunResults()" [disabled]="!runId">刷新结果</button>
        </div>

        <dl class="facts">
          <div><dt>条件状态</dt><dd>{{ planConfirmed ? '已确认' : '待确认' }}</dd></div>
          <div><dt>批次编号</dt><dd>{{ runId || '-' }}</dd></div>
          <div><dt>批次状态</dt><dd>{{ statusLabel(runStatus) }}</dd></div>
          <div><dt>候选人数</dt><dd>{{ candidateCount || 0 }}</dd></div>
        </dl>

        <p class="banner success" *ngIf="stepMessage">{{ stepMessage }}</p>
        <p class="banner error" *ngIf="friendlyErrorMessage()">{{ friendlyErrorMessage() }}</p>
      </article>

      <article class="panel">
        <div class="step-title"><span>4</span><h3>浏览候选人</h3></div>
        <div *ngIf="snapshots.length; else noSnapshots">
          <div class="snapshot" *ngFor="let snapshot of snapshots">
            <h4>结果页 {{ snapshot.pageNo }} · {{ statusLabel(snapshot.status) }}</h4>
            <p>共 {{ snapshot.total }} 位候选人</p>
            <p class="hint" *ngIf="snapshotMessage(snapshot)">{{ snapshotMessage(snapshot) }}</p>
            <button *ngFor="let candidate of snapshot.candidates" (click)="loadCandidate(candidate.candidateId)">
              {{ candidate.name }} · {{ candidate.title }} · {{ candidate.company }}
            </button>
          </div>
          <p class="hint" *ngIf="runStatus === 'completed' && !candidateCount">当前没有命中候选人。请调整关键词、城市、年限或目标范围后再试一次。</p>
        </div>
        <ng-template #noSnapshots>
          <p class="hint">发起寻访后，这里会显示候选人结果。</p>
        </ng-template>
      </article>
    </section>

    <section class="panel detail" *ngIf="selectedCandidate">
      <div class="step-title"><span>5</span><h3>简历要点</h3></div>
      <div class="detail-grid">
        <div>
          <p><strong>{{ selectedCandidate.candidate.name }}</strong> · {{ selectedCandidate.candidate.title }}</p>
          <p class="hint">{{ selectedCandidate.candidate.company }} · {{ selectedCandidate.candidate.location }}</p>
          <p>{{ selectedCandidate.aiAnalysis.summary }}</p>

          <div class="chips" *ngIf="displayEvidenceSpans().length">
            <span *ngFor="let evidence of displayEvidenceSpans()">{{ evidence }}</span>
          </div>
          <div class="chips warning" *ngIf="displayRiskFlags().length">
            <span *ngFor="let risk of displayRiskFlags()">{{ risk }}</span>
          </div>
        </div>

        <dl class="facts">
          <div *ngFor="let item of resumeMetaItems()">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </div>

      <div class="resume-block" *ngIf="resumeEducationList().length">
        <h4>教育经历</h4>
        <ul>
          <li *ngFor="let item of resumeEducationList()">
            {{ item['schoolName'] || item['school'] || '未提供学校' }} · {{ item['degree'] || item['education'] || '学历未知' }} · {{ item['major'] || item['speciality'] || '专业未知' }}
          </li>
        </ul>
      </div>

      <div class="resume-block" *ngIf="resumeWorkExperienceList().length">
        <h4>工作经历</h4>
        <ul>
          <li *ngFor="let item of resumeWorkExperienceList()">
            {{ item['companyName'] || item['company'] || '未提供公司' }} · {{ item['positionName'] || item['title'] || item['position'] || '职位未知' }}
          </li>
        </ul>
      </div>

      <div class="resume-block" *ngIf="resumeSummaryList().length">
        <h4>经历摘要</h4>
        <ul>
          <li *ngFor="let item of resumeSummaryList()">{{ item }}</li>
        </ul>
      </div>

      <div class="resume-block" *ngIf="projectNameList().length">
        <h4>项目关键词</h4>
        <div class="chips">
          <span *ngFor="let item of projectNameList()">{{ item }}</span>
        </div>
      </div>

      <div class="step-title compact"><span>6</span><h3>给出结论</h3></div>
      <div class="actions">
        <button (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.MATCH)">推荐</button>
        <button class="secondary" (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.MAYBE)">可再看</button>
        <button class="secondary" (click)="saveVerdict(selectedCandidate.candidate.candidateId, verdictEnum.NO)">不推荐</button>
      </div>
      <p class="banner success" *ngIf="verdictMessage">{{ verdictMessage }}</p>

      <div class="step-title compact"><span>7</span><h3>历史判断</h3></div>
      <ul class="history" *ngIf="selectedCandidate.verdictHistory.length; else noHistory">
        <li *ngFor="let item of selectedCandidate.verdictHistory">
          {{ formatTime(item.createdAt) }} · {{ decisionLabel(item.verdict) }} · {{ reasonLabels(item.reasons) }}
        </li>
      </ul>
      <ng-template #noHistory>
        <p class="hint">当前还没有历史判断记录。</p>
      </ng-template>
    </section>

    <section class="panel">
      <div class="step-title"><span>8</span><h3>导出名单</h3></div>
      <p class="hint">导出当前岗位下已标记为“推荐”或“可再看”的候选人短名单。</p>
      <div class="actions">
        <button (click)="exportMasked()" [disabled]="!caseId">导出短名单</button>
      </div>
      <dl class="facts">
        <div><dt>导出状态</dt><dd>{{ exportStatusLabel() }}</dd></div>
        <div><dt>导出文件</dt><dd>{{ exportFileName() }}</dd></div>
      </dl>
    </section>
  `,
  styles: [`
    .hero { margin-bottom: 20px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
    .panel { padding: 20px; border-radius: 24px; background: rgba(255,255,255,0.92); border: 1px solid rgba(17,32,51,0.08); box-shadow: 0 16px 36px rgba(17,32,51,0.08); }
    .detail { margin-top: 20px; }
    h2, h3, h4 { margin-top: 0; }
    .step-title { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
    .step-title span { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 999px; background: #0f766e; color: #fff; font-weight: 700; }
    .step-title.compact { margin-top: 24px; }
    label { display: block; margin: 14px 0 6px; font-size: 13px; color: #475569; }
    input, textarea { width: 100%; border-radius: 16px; border: 1px solid rgba(17,32,51,0.12); padding: 12px 14px; background: #fff; }
    textarea { resize: vertical; }
    .actions { display: flex; gap: 12px; margin-top: 16px; flex-wrap: wrap; }
    button { border: 0; border-radius: 999px; padding: 10px 16px; background: #112033; color: #fff; cursor: pointer; }
    button.secondary { background: #dbe6f7; color: #112033; }
    button:disabled { opacity: 0.4; cursor: default; }
    .facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .compact-facts { margin-top: 18px; }
    .facts div { padding: 12px; border-radius: 16px; background: #f4f7fb; }
    dt { font-size: 12px; color: #64748b; }
    dd { margin: 4px 0 0; font-family: 'IBM Plex Mono', monospace; }
    .filters-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
    .snapshot { padding: 12px; border-radius: 16px; background: #f8fafc; margin-bottom: 12px; }
    .snapshot button { display: block; width: 100%; margin-top: 8px; text-align: left; background: #fff; color: #112033; border: 1px solid rgba(17,32,51,0.08); }
    .detail-grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; }
    .resume-block { margin-top: 20px; padding: 16px; border-radius: 16px; background: #f8fafc; }
    .resume-block ul { margin: 0; padding-left: 18px; }
    .chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
    .chips span { padding: 6px 10px; border-radius: 999px; background: #dbeafe; color: #0f172a; font-size: 13px; }
    .chips.warning span { background: #fef3c7; color: #92400e; }
    .banner { margin-top: 16px; padding: 12px 14px; border-radius: 16px; }
    .banner.success { background: #ecfeff; color: #0f766e; }
    .banner.error { background: #fef2f2; color: #b91c1c; }
    .history { padding-left: 18px; }
    .hint { color: #475569; }
    @media (max-width: 900px) {
      .grid { grid-template-columns: 1fr; }
      .filters-grid { grid-template-columns: 1fr; }
      .detail-grid { grid-template-columns: 1fr; }
    }
  `]
})
export class CasesPageComponent implements OnDestroy {
  readonly verdictEnum = Verdict;
  private readonly pollingIntervalMs = 1200;
  private readonly pollingTimeoutMs = 60000;
  private pollingTimer: ReturnType<typeof setTimeout> | null = null;
  private pollingDeadline = 0;

  title = '在线教育算法工程师';
  ownerTeamId = 'team-cn';
  jdText = '请填写岗位说明。';
  mustTermsText = '';
  shouldTermsText = '';
  excludeTermsText = '';
  locationText = '';
  degreeText = '';
  schoolTypeText = '';
  workExperienceRangeText = '';
  positionText = '';
  workContentText = '';
  companyText = '';
  schoolText = '';
  pageSizeText = '10';
  pageBudgetText = '1';

  caseId = '';
  jdVersionId = '';
  planId = '';
  runId = '';
  runStatus = '';
  runError = '';
  exportStatus = '';
  exportFilePath = '';
  planConfirmed = false;
  stepMessage = '';
  errorMessage = '';
  verdictMessage = '';
  draft: ConditionPlanDraft | null = null;
  snapshots: SearchRunPageSnapshot[] = [];
  selectedCandidate: CandidateDetailResponse | null = null;
  latestVerdict: string | null = null;

  constructor(private readonly api: PlatformApiService) {}

  ngOnDestroy(): void {
    this.stopRunPolling();
  }

  get candidateCount(): number {
    return this.snapshots.reduce((count, snapshot) => count + snapshot.candidates.length, 0);
  }

  async createCaseAndJd(): Promise<void> {
    this.resetForNewCase();
    this.errorMessage = '';
    this.stepMessage = '';

    const caseResult = await this.api.createCase(this.title, this.ownerTeamId);
    this.caseId = caseResult.caseId;

    const version = await this.api.createJdVersion(this.caseId, this.jdText, 'manual');
    this.jdVersionId = version.jdVersionId;
    this.stepMessage = '岗位需求已保存，可以生成一版寻访建议。';
  }

  async generateDraft(): Promise<void> {
    if (!this.caseId || !this.jdVersionId) {
      return;
    }
    this.errorMessage = '';
    this.stepMessage = '';

    const draftJob = await this.api.createKeywordDraft(this.caseId, this.jdVersionId);
    this.planId = draftJob.planId;
    this.draft = draftJob.draft;
    this.applyDraftToEditors(draftJob.draft);
    this.planConfirmed = false;
    this.stepMessage = '寻访建议已生成，请检查后确认筛选条件。';
  }

  async confirmPlan(): Promise<void> {
    if (!this.planId || !this.draft) {
      return;
    }
    this.errorMessage = '';
    this.stepMessage = '';

    const draft = this.buildDraft();
    const confirmed = await this.api.confirmPlan(this.planId, draft, 'consultant-web');
    this.planId = confirmed.planId;
    this.draft = draft;
    this.planConfirmed = true;
    this.stepMessage = '筛选条件已确认，可以开始寻访。';
  }

  async createSearchRun(): Promise<void> {
    if (!this.caseId || !this.planId) {
      return;
    }
    this.errorMessage = '';
    this.stepMessage = '';
    this.runError = '';
    this.snapshots = [];
    this.selectedCandidate = null;
    this.latestVerdict = null;
    this.verdictMessage = '';
    this.stopRunPolling();

    const run = await this.api.createSearchRun(this.caseId, this.planId, this.readNumber(this.pageBudgetText, 1));
    this.runId = run.runId;
    this.runStatus = run.status;
    this.stepMessage = '正在整理候选人，请稍候。';
    await this.refreshRunResults(false);
    if (this.runStatus === 'queued' || this.runStatus === 'running') {
      this.startRunPolling();
    }
  }

  async refreshRunResults(manualRefresh = true): Promise<void> {
    if (!this.runId) {
      return;
    }

    const status = await this.api.getSearchRun(this.runId);
    this.runStatus = status.status;
    this.runError = status.errorSummary ?? '';

    const pages = await this.api.getSearchRunPages(this.runId);
    this.snapshots = pages.snapshots;
    this.errorMessage = this.snapshots.find((snapshot) => snapshot.errorMessage)?.errorMessage ?? '';
    if (this.runStatus === 'completed') {
      this.stepMessage = '本批寻访已完成，可以开始浏览候选人。';
      this.stopRunPolling();
      return;
    }
    if (this.runStatus === 'failed') {
      this.stepMessage = '本批寻访未能完成，请调整筛选条件后重试。';
      this.stopRunPolling();
      return;
    }
    if (manualRefresh) {
      this.stepMessage = '当前仍在整理候选人，请稍后再刷新。';
      this.startRunPolling();
    }
  }

  async loadCandidate(candidateId: string): Promise<void> {
    this.selectedCandidate = await this.api.getCandidate(candidateId);
    this.verdictMessage = '';
  }

  async saveVerdict(candidateId: string, verdict: Verdict): Promise<void> {
    const response = await this.api.saveVerdict(candidateId, verdict, 'updated in candidate review');
    this.latestVerdict = response.latestVerdict;
    this.verdictMessage = `已记录结论：${this.decisionLabel(response.latestVerdict)}。`;
    if (this.selectedCandidate) {
      this.selectedCandidate = await this.api.getCandidate(candidateId);
    }
  }

  async exportMasked(): Promise<void> {
    if (!this.caseId) {
      return;
    }
    const result = await this.api.createExport(this.caseId);
    this.exportStatus = result.status;
    this.exportFilePath = result.filePath ?? '';
  }

  conditionSummaryItems(): Array<{ label: string; value: string }> {
    return [
      { label: '重点关键词', value: this.readList(this.mustTermsText, '\n').join(' / ') || '未填写' },
      { label: '加分关键词', value: this.readList(this.shouldTermsText, '\n').join(' / ') || '未填写' },
      { label: '意向城市', value: this.locationText || '未填写' },
      { label: '工作年限', value: this.workExperienceRangeText || '未填写' },
      { label: '每页人数', value: this.pageSizeText || '10' },
      { label: '拉取页数', value: this.pageBudgetText || '1' }
    ];
  }

  friendlyErrorMessage(): string {
    const message = this.errorMessage || this.runError;
    if (!message) {
      return '';
    }
    if (message.includes('CTS tenant credentials')) {
      return '搜索服务尚未配置完成，请联系管理员。';
    }
    if (message.includes('authentication failed')) {
      return '搜索服务认证失败，请联系管理员检查配置。';
    }
    if (message.includes('data:null')) {
      return '当前条件没有返回有效结果，请放宽关键词、城市或年限后重试。';
    }
    if (message.includes('network error')) {
      return '搜索服务暂时不可用，请稍后再试。';
    }
    return '当前批次未能顺利完成，请调整条件后再试一次。';
  }

  snapshotMessage(snapshot: SearchRunPageSnapshot): string {
    if (!snapshot.errorMessage) {
      return '';
    }
    this.errorMessage = snapshot.errorMessage;
    return this.friendlyErrorMessage();
  }

  statusLabel(status: string): string {
    switch (status) {
      case 'draft':
        return '待确认';
      case 'confirmed':
        return '已确认';
      case 'queued':
        return '待开始';
      case 'running':
        return '进行中';
      case 'completed':
        return '已完成';
      case 'failed':
        return '失败';
      default:
        return status || '-';
    }
  }

  exportStatusLabel(): string {
    if (!this.exportStatus) {
      return '-';
    }
    return this.statusLabel(this.exportStatus);
  }

  resumeEducationList(): ResumeRecord[] {
    const items = this.extractResumeContent()['educationList'];
    return Array.isArray(items) ? items.filter((item) => this.isRecord(item)) : [];
  }

  resumeWorkExperienceList(): ResumeRecord[] {
    const items = this.extractResumeContent()['workExperienceList'];
    return Array.isArray(items) ? items.filter((item) => this.isRecord(item)) : [];
  }

  resumeSummaryList(): string[] {
    return this.stringList(this.extractResumeContent()['workSummariesAll']).slice(0, 5);
  }

  projectNameList(): string[] {
    return this.stringList(this.extractResumeContent()['projectNameAll']).slice(0, 8);
  }

  resumeMetaItems(): Array<{ label: string; value: string }> {
    const resume = this.extractResumeContent();
    return [
      { label: '工作年限', value: this.stringValue(resume['workYear']) },
      { label: '当前城市', value: this.stringValue(resume['nowLocation']) },
      { label: '意向城市', value: this.stringValue(resume['expectedLocation']) },
      { label: '当前状态', value: this.stringValue(resume['jobState']) },
      { label: '期望薪资', value: this.stringValue(resume['expectedSalary']) },
      { label: '年龄', value: this.stringValue(resume['age']) }
    ].filter((item) => item.value);
  }

  displayEvidenceSpans(): string[] {
    return (this.selectedCandidate?.aiAnalysis.evidenceSpans ?? []).slice(0, 5);
  }

  displayRiskFlags(): string[] {
    return (this.selectedCandidate?.aiAnalysis.riskFlags ?? []).map((flag) => this.riskFlagLabel(flag));
  }

  decisionLabel(verdict: string | null | undefined): string {
    switch (verdict) {
      case Verdict.MATCH:
      case 'Match':
        return '推荐';
      case Verdict.MAYBE:
      case 'Maybe':
        return '可再看';
      case Verdict.NO:
      case 'No':
        return '不推荐';
      default:
        return '未判断';
    }
  }

  reasonLabels(reasons: string[]): string {
    if (!reasons.length) {
      return '人工判断';
    }
    return reasons
      .map((reason) => {
        if (reason === 'manual review') {
          return '人工判断';
        }
        if (reason === 'core fit') {
          return '核心要求匹配';
        }
        return reason;
      })
      .join(' / ');
  }

  formatTime(value: string): string {
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false });
  }

  exportFileName(): string {
    if (!this.exportFilePath) {
      return '-';
    }
    const parts = this.exportFilePath.split('/');
    return parts[parts.length - 1] || this.exportFilePath;
  }

  private applyDraftToEditors(draft: ConditionPlanDraft): void {
    this.mustTermsText = draft.mustTerms.join('\n');
    this.shouldTermsText = draft.shouldTerms.join('\n');
    this.excludeTermsText = draft.excludeTerms.join('\n');

    const filters = draft.structuredFilters ?? {};
    const location = filters['location'];
    this.locationText = Array.isArray(location) ? location.join(', ') : '';
    this.degreeText = this.stringValue(filters['degree']);
    this.schoolTypeText = this.stringValue(filters['schoolType']);
    this.workExperienceRangeText = this.stringValue(filters['workExperienceRange']);
    this.positionText = this.stringValue(filters['position']);
    this.workContentText = this.stringValue(filters['workContent']);
    this.companyText = this.stringValue(filters['company']);
    this.schoolText = this.stringValue(filters['school']);
    this.pageSizeText = this.stringValue(filters['pageSize']) || '10';
    this.pageBudgetText = this.pageBudgetText || '1';
  }

  private buildDraft(): ConditionPlanDraft {
    const structuredFilters: Record<string, unknown> = {
      page: 1,
      pageSize: this.readNumber(this.pageSizeText, 10)
    };
    const location = this.readList(this.locationText, ',');
    if (location.length) {
      structuredFilters['location'] = location;
    }

    this.applyOptionalNumber(structuredFilters, 'degree', this.degreeText);
    this.applyOptionalNumber(structuredFilters, 'schoolType', this.schoolTypeText);
    this.applyOptionalNumber(structuredFilters, 'workExperienceRange', this.workExperienceRangeText);
    this.applyOptionalString(structuredFilters, 'position', this.positionText);
    this.applyOptionalString(structuredFilters, 'workContent', this.workContentText);
    this.applyOptionalString(structuredFilters, 'company', this.companyText);
    this.applyOptionalString(structuredFilters, 'school', this.schoolText);

    return {
      mustTerms: this.readList(this.mustTermsText, '\n'),
      shouldTerms: this.readList(this.shouldTermsText, '\n'),
      excludeTerms: this.readList(this.excludeTermsText, '\n'),
      structuredFilters,
      evidenceRefs: this.draft?.evidenceRefs ?? []
    };
  }

  private applyOptionalString(target: Record<string, unknown>, key: string, raw: string): void {
    const value = raw.trim();
    if (value) {
      target[key] = value;
    }
  }

  private applyOptionalNumber(target: Record<string, unknown>, key: string, raw: string): void {
    const value = raw.trim();
    if (!value) {
      return;
    }
    const parsed = Number(value);
    if (!Number.isNaN(parsed)) {
      target[key] = parsed;
    }
  }

  private readList(raw: string, delimiter: string): string[] {
    if (!raw.trim()) {
      return [];
    }
    return raw
      .split(delimiter)
      .map((item) => item.trim())
      .filter(Boolean);
  }

  private readNumber(raw: string, fallback: number): number {
    const parsed = Number(raw);
    return Number.isNaN(parsed) ? fallback : parsed;
  }

  private extractResumeContent(): ResumeRecord {
    const snapshotContent = this.selectedCandidate?.resumeSnapshot.content;
    if (!snapshotContent) {
      return {};
    }
    const nested = snapshotContent['content'];
    if (this.isRecord(nested)) {
      return nested;
    }
    return this.isRecord(snapshotContent) ? snapshotContent : {};
  }

  private stringValue(value: unknown): string {
    if (typeof value === 'string') {
      return value;
    }
    if (typeof value === 'number') {
      return String(value);
    }
    return '';
  }

  private stringList(value: unknown): string[] {
    if (typeof value === 'string') {
      return [value];
    }
    if (Array.isArray(value)) {
      return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
    }
    return [];
  }

  private riskFlagLabel(flag: string): string {
    if (flag.startsWith('Expected salary: ')) {
      return `期望薪资：${flag.replace('Expected salary: ', '')}`;
    }
    if (flag.startsWith('Job state: ')) {
      return `当前状态：${flag.replace('Job state: ', '')}`;
    }
    return flag;
  }

  private isRecord(value: unknown): value is ResumeRecord {
    return typeof value === 'object' && value !== null && !Array.isArray(value);
  }

  private resetForNewCase(): void {
    this.stopRunPolling();
    this.caseId = '';
    this.jdVersionId = '';
    this.planId = '';
    this.runId = '';
    this.runStatus = '';
    this.runError = '';
    this.exportStatus = '';
    this.exportFilePath = '';
    this.planConfirmed = false;
    this.draft = null;
    this.snapshots = [];
    this.selectedCandidate = null;
    this.latestVerdict = null;
    this.verdictMessage = '';
  }

  private startRunPolling(): void {
    if (!this.runId) {
      return;
    }
    this.stopRunPolling();
    this.pollingDeadline = Date.now() + this.pollingTimeoutMs;
    this.scheduleNextPoll();
  }

  private scheduleNextPoll(): void {
    if (!this.runId || this.pollingTimer !== null) {
      return;
    }
    this.pollingTimer = setTimeout(async () => {
      this.pollingTimer = null;
      await this.pollRunStatus();
    }, this.pollingIntervalMs);
  }

  private async pollRunStatus(): Promise<void> {
    if (!this.runId) {
      return;
    }
    try {
      await this.refreshRunResults(false);
    } catch {
      this.errorMessage = '当前批次结果暂时无法刷新，请稍后再试。';
      this.stopRunPolling();
      return;
    }

    if (this.runStatus === 'completed' || this.runStatus === 'failed') {
      return;
    }
    if (Date.now() >= this.pollingDeadline) {
      this.stepMessage = '仍在整理候选人，你可以稍后点击“刷新结果”继续查看。';
      this.stopRunPolling();
      return;
    }
    this.scheduleNextPoll();
  }

  private stopRunPolling(): void {
    if (this.pollingTimer !== null) {
      clearTimeout(this.pollingTimer);
      this.pollingTimer = null;
    }
    this.pollingDeadline = 0;
  }
}
