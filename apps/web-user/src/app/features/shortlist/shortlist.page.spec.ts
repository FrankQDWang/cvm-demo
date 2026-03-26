import { TestBed } from '@angular/core/testing';

import {
  AgentRuntimeConfigEntry,
  type AgentRunResponse,
  type AgentShortlistCandidate,
  type CandidateDetailResponse,
  PlatformApiService,
} from '@cvm/platform-api-client';

import { ShortlistPageComponent } from './shortlist.page';

function buildCandidate(): AgentShortlistCandidate {
  return {
    candidateId: 'cand_1',
    externalIdentityId: 'resume_1',
    name: '匿名候选人-1',
    title: 'Senior Java Engineer',
    company: 'CVM',
    location: 'Beijing',
    summary: 'Java, React, BPM',
    reason: '与岗位要求高度匹配。',
    score: 0.94,
    sourceRound: 1,
  };
}

function buildRunResponse(candidate: AgentShortlistCandidate): AgentRunResponse {
  return {
    runId: 'run_1',
    caseId: 'case_1',
    status: 'completed',
    jdText: 'JD',
    sourcingPreferenceText: '偏好',
    config: { maxRounds: 3, roundFetchSchedule: [10, 5, 5], finalTopK: 5 },
    currentRound: 3,
    modelVersion: 'gpt-5.4-mini',
    agentRuntimeConfig: {
      strategyExtractor: { modelVersion: 'gpt-5.4-mini', thinkingEffort: AgentRuntimeConfigEntry.thinkingEffort.LOW },
      resumeMatcher: { modelVersion: 'gpt-5.4-mini', thinkingEffort: AgentRuntimeConfigEntry.thinkingEffort.LOW },
      searchReflector: { modelVersion: 'gpt-5.4', thinkingEffort: AgentRuntimeConfigEntry.thinkingEffort.MEDIUM },
    },
    promptVersion: 'agent-loop-v1',
    workflowId: 'agent-run-run_1',
    temporalNamespace: 'default',
    temporalTaskQueue: 'cvm-agent-runs',
    langfuseTraceId: null,
    langfuseTraceUrl: null,
    steps: [],
    finalShortlist: [candidate],
    seenResumeIds: ['resume_1'],
    errorCode: null,
    errorMessage: null,
    createdAt: '2026-03-26T00:00:00Z',
    startedAt: '2026-03-26T00:00:00Z',
    finishedAt: '2026-03-26T00:03:00Z',
  };
}

function buildCandidateDetail(): CandidateDetailResponse {
  return {
    candidate: {
      candidateId: 'cand_1',
      externalIdentityId: 'resume_1',
      name: '匿名候选人-1',
      title: 'Senior Java Engineer',
      company: 'CVM',
      location: 'Beijing',
      summary: 'Java, React, BPM',
    },
    resumeView: {
      snapshotId: 'snap_1',
      projection: {
        workYear: 9,
        currentLocation: 'Beijing',
        expectedLocation: 'Beijing',
        jobState: 'OpenToWork',
        expectedSalary: '45k-60k',
        age: 32,
        education: [],
        workExperience: [],
        workSummaries: ['Built workflow platforms.'],
        projectNames: ['BPM Platform'],
      },
    },
    aiAnalysis: {
      status: 'completed',
      summary: 'Strong fit',
      evidenceSpans: ['Java', 'React'],
      riskFlags: [],
    },
    verdictHistory: [],
  };
}

describe('ShortlistPageComponent', () => {
  const candidate = buildCandidate();
  const candidateDetail = buildCandidateDetail();
  let api: jasmine.SpyObj<PlatformApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<PlatformApiService>('PlatformApiService', [
      'createAgentRun',
      'getAgentRun',
      'getCaseCandidate',
    ]);

    await TestBed.configureTestingModule({
      imports: [ShortlistPageComponent],
      providers: [{ provide: PlatformApiService, useValue: api }],
    }).compileComponents();
  });

  it('loads shortlist rows after a completed run', async () => {
    const fixture = TestBed.createComponent(ShortlistPageComponent);
    const component = fixture.componentInstance;
    component.jdText = 'JD';
    component.sourcingPreferenceText = '偏好';
    api.createAgentRun.and.resolveTo({ runId: 'run_1', status: 'queued' });
    api.getAgentRun.and.resolveTo(buildRunResponse(candidate));

    await component.startRun();

    expect(component.shortlist.length).toBe(1);
    const row = component.shortlist[0];
    expect(row).toBeDefined();
    expect(row.candidate.candidateId).toBe('cand_1');
    expect(component.statusLine).toContain('返回 1 份简历');
  });

  it('loads candidate detail once and reuses the cached resume on re-expand', async () => {
    const fixture = TestBed.createComponent(ShortlistPageComponent);
    const component = fixture.componentInstance;
    component.shortlist = [{ rank: 1, candidate }];
    const row = component.shortlist[0];
    expect(row).toBeDefined();
    api.getCaseCandidate.and.resolveTo(candidateDetail);

    await component.toggleResume(row);
    await component.toggleResume(row);
    await component.toggleResume(row);

    expect(api.getCaseCandidate.calls.count()).toBe(1);
    expect(component.resumeDetailState(row).status).toBe('loaded');
    expect(component.resumeProjection(row)?.projectNames).toEqual(['BPM Platform']);
  });

  it('surfaces detail loading errors in the expanded resume panel state', async () => {
    const fixture = TestBed.createComponent(ShortlistPageComponent);
    const component = fixture.componentInstance;
    component.shortlist = [{ rank: 1, candidate }];
    const row = component.shortlist[0];
    expect(row).toBeDefined();
    api.getCaseCandidate.and.returnValue(Promise.reject(new Error('candidate detail failed')));

    await component.toggleResume(row);

    expect(component.resumeDetailState(row).status).toBe('error');
    expect(component.resumeDetailState(row).error).toContain('candidate detail failed');
  });
});
