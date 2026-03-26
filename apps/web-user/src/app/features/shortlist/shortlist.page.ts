import { CommonModule } from '@angular/common';
import { Component, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import {
  type AgentRunResponse,
  type AgentShortlistCandidate,
  type CandidateDetailResponse,
  PlatformApiService,
} from '@cvm/platform-api-client';

const POLL_INTERVAL_MS = 2_500;

type DetailLoadStatus = 'idle' | 'loading' | 'loaded' | 'error';

type ShortlistRow = {
  rank: number;
  candidate: AgentShortlistCandidate;
};

type DetailCacheEntry = {
  status: DetailLoadStatus;
  detail: CandidateDetailResponse | null;
  error: string;
};

type ResumeProjection = CandidateDetailResponse['resumeView']['projection'];

@Component({
  selector: 'app-shortlist-page',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './shortlist.page.html',
  styleUrl: './shortlist.page.css',
})
export class ShortlistPageComponent implements OnDestroy {
  private readonly api = inject(PlatformApiService);
  private pollTimer: number | null = null;

  jdText = '';
  sourcingPreferenceText = '';

  runId = '';
  runStatus = 'idle';
  statusLine = '';
  errorMessage = '';
  traceUrl = '';

  isStarting = false;
  isPolling = false;

  shortlist: ShortlistRow[] = [];
  expandedCandidateId: string | null = null;
  private detailCache: Record<string, DetailCacheEntry> = {};

  ngOnDestroy(): void {
    this.stopPolling();
  }

  get canStart(): boolean {
    return !this.isStarting && this.jdText.trim().length > 0 && this.sourcingPreferenceText.trim().length > 0;
  }

  get hasShortlist(): boolean {
    return this.shortlist.length > 0;
  }

  async startRun(): Promise<void> {
    if (!this.canStart) {
      return;
    }

    this.resetRunState();
    this.isStarting = true;
    this.statusLine = '正在启动 Agent';

    try {
      const created = await this.api.createAgentRun({
        jdText: this.jdText.trim(),
        sourcingPreferenceText: this.sourcingPreferenceText.trim(),
      });
      this.runId = created.runId;
      this.runStatus = created.status;
      await this.refreshRun();
    } catch (error: unknown) {
      this.handleRunError(error);
    } finally {
      this.isStarting = false;
    }
  }

  candidateMeta(candidate: AgentShortlistCandidate): string {
    return [candidate.title, candidate.company, candidate.location].filter(Boolean).join(' · ');
  }

  candidateScore(candidate: AgentShortlistCandidate): string {
    return `${String(Math.round(candidate.score * 100))}%`;
  }

  trackShortlist(_: number, row: ShortlistRow): string {
    return row.candidate.candidateId;
  }

  isResumeExpanded(row: ShortlistRow): boolean {
    return this.expandedCandidateId === row.candidate.candidateId;
  }

  resumeToggleLabel(row: ShortlistRow): string {
    return this.isResumeExpanded(row) ? '收起简历' : '查看完整简历';
  }

  resumeToggleIcon(row: ShortlistRow): string {
    return this.isResumeExpanded(row) ? '-' : '+';
  }

  resumeDetailState(row: ShortlistRow): DetailCacheEntry {
    return this.detailCache[row.candidate.candidateId] ?? EMPTY_DETAIL_CACHE_ENTRY;
  }

  resumeProjection(row: ShortlistRow): ResumeProjection | null {
    return this.resumeDetailState(row).detail?.resumeView.projection ?? null;
  }

  async toggleResume(row: ShortlistRow): Promise<void> {
    const candidateId = row.candidate.candidateId;
    if (this.expandedCandidateId === candidateId) {
      this.expandedCandidateId = null;
      return;
    }
    this.expandedCandidateId = candidateId;
    await this.ensureCandidateDetail(row.candidate);
  }

  async retryResume(row: ShortlistRow, event?: Event): Promise<void> {
    event?.stopPropagation();
    await this.loadCandidateDetail(row.candidate, { force: true });
  }

  fallbackText(value: string | number | null | undefined): string {
    if (value === null || value === undefined) {
      return '未提供';
    }
    const normalized = String(value).trim();
    return normalized.length > 0 ? normalized : '未提供';
  }

  workExperience(row: ShortlistRow) {
    return this.resumeProjection(row)?.workExperience ?? [];
  }

  educationItems(row: ShortlistRow) {
    return this.resumeProjection(row)?.education ?? [];
  }

  workSummaries(row: ShortlistRow): string[] {
    return this.resumeProjection(row)?.workSummaries ?? [];
  }

  projectNames(row: ShortlistRow): string[] {
    return this.resumeProjection(row)?.projectNames ?? [];
  }

  resumeOverview(row: ShortlistRow): Array<{ label: string; value: string }> {
    const projection = this.resumeProjection(row);
    return [
      { label: '工作年限', value: this.fallbackText(projection?.workYear) },
      { label: '当前地点', value: this.fallbackText(projection?.currentLocation) },
      { label: '期望地点', value: this.fallbackText(projection?.expectedLocation) },
      { label: '求职状态', value: this.fallbackText(projection?.jobState) },
      { label: '期望薪资', value: this.fallbackText(projection?.expectedSalary) },
      { label: '年龄', value: this.fallbackText(projection?.age) },
    ];
  }

  workExperienceMeta(startTime: string | null, endTime: string | null, duration: string | null): string {
    if (duration?.trim()) {
      return duration;
    }
    const start = startTime?.trim() || '未提供';
    const end = endTime?.trim() || '至今';
    return `${start} - ${end}`;
  }

  private async refreshRun(): Promise<void> {
    if (!this.runId || this.isPolling) {
      return;
    }

    this.isPolling = true;
    this.errorMessage = '';

    try {
      const run = await this.api.getAgentRun(this.runId);
      this.syncRunState(run);
    } catch (error: unknown) {
      this.handleRunError(error);
    } finally {
      this.isPolling = false;
      if (this.shouldPoll()) {
        this.schedulePoll();
      } else {
        this.stopPolling();
      }
    }
  }

  private syncRunState(run: AgentRunResponse): void {
    this.runStatus = run.status;
    this.traceUrl = run.langfuseTraceUrl ?? '';
    const normalized = normalizeStatus(run.status);

    if (normalized === 'failed') {
      throw new Error(run.errorMessage?.trim() || '运行失败，请稍后重试。');
    }

    if (normalized === 'completed') {
      this.shortlist = run.finalShortlist.map((candidate, index) => ({
        rank: index + 1,
        candidate,
      }));
      this.statusLine =
        this.shortlist.length > 0
          ? `已完成 · 返回 ${String(this.shortlist.length)} 份简历`
          : '已完成 · 没有找到候选人';
      return;
    }

    this.statusLine = buildRunningStatus(run);
  }

  private shouldPoll(): boolean {
    const normalized = normalizeStatus(this.runStatus);
    return this.runId.length > 0 && (normalized === 'queued' || normalized === 'running');
  }

  private schedulePoll(): void {
    this.stopPolling();
    this.pollTimer = window.setTimeout(() => {
      this.pollTimer = null;
      void this.refreshRun();
    }, POLL_INTERVAL_MS);
  }

  private stopPolling(): void {
    if (this.pollTimer !== null) {
      window.clearTimeout(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private resetRunState(): void {
    this.stopPolling();
    this.runId = '';
    this.runStatus = 'idle';
    this.statusLine = '';
    this.errorMessage = '';
    this.traceUrl = '';
    this.isPolling = false;
    this.shortlist = [];
    this.expandedCandidateId = null;
    this.detailCache = {};
  }

  private handleRunError(error: unknown): void {
    this.stopPolling();
    this.runStatus = 'failed';
    this.statusLine = '';
    this.errorMessage = describeError(error);
  }

  private async ensureCandidateDetail(candidate: AgentShortlistCandidate): Promise<void> {
    const cached = this.detailCache[candidate.candidateId];
    if (cached?.status === 'loaded' || cached?.status === 'loading') {
      return;
    }
    await this.loadCandidateDetail(candidate);
  }

  private async loadCandidateDetail(
    candidate: AgentShortlistCandidate,
    options?: { force?: boolean },
  ): Promise<void> {
    const candidateId = candidate.candidateId;
    if (!options?.force) {
      const cached = this.detailCache[candidateId];
      if (cached?.status === 'loaded' || cached?.status === 'loading') {
        return;
      }
    }
    this.detailCache[candidateId] = {
      status: 'loading',
      detail: null,
      error: '',
    };
    try {
      const detail = await this.api.getCaseCandidate(candidateId);
      this.detailCache[candidateId] = {
        status: 'loaded',
        detail,
        error: '',
      };
    } catch (error: unknown) {
      this.detailCache[candidateId] = {
        status: 'error',
        detail: null,
        error: describeError(error),
      };
    }
  }
}

const EMPTY_DETAIL_CACHE_ENTRY: DetailCacheEntry = {
  status: 'idle',
  detail: null,
  error: '',
};

function normalizeStatus(status: string): string {
  return status.trim().toLowerCase();
}

function buildRunningStatus(run: AgentRunResponse): string {
  const roundLabel = run.currentRound > 0 ? `第 ${String(run.currentRound)} 轮` : '准备中';
  return `${roundLabel} · Agent 正在执行`;
}

function describeError(error: unknown): string {
  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }
  return '请求失败，请稍后重试。';
}
