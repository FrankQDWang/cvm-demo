import { Injectable } from '@angular/core';

import {
  CreateExportRequest,
  type CandidateDetailResponse,
  type ConditionPlanDraft,
  type ConfirmConditionPlanResponse,
  type CreateCaseResponse,
  type CreateEvalRunResponse,
  type CreateExportResponse,
  type CreateJdVersionResponse,
  type CreateKeywordDraftJobResponse,
  type CreateSearchRunResponse,
  DefaultService,
  type OpsSummaryResponse,
  OpenAPI,
  type SearchRunPagesResponse,
  type SearchRunStatusResponse,
  type TemporalSearchRunDiagnosticResponse,
  Verdict,
} from '@cvm/api-client-generated';

type RuntimeConfig = {
  apiBaseUrl?: string;
};

let isConfigured = false;

function configureOpenApiBase(): void {
  if (isConfigured) {
    return;
  }
  const runtimeConfig = (globalThis as typeof globalThis & { __CVM_RUNTIME_CONFIG__?: RuntimeConfig }).__CVM_RUNTIME_CONFIG__;
  OpenAPI.BASE = runtimeConfig?.apiBaseUrl ?? 'http://localhost:8010';
  isConfigured = true;
}

@Injectable({ providedIn: 'root' })
export class PlatformApiService {
  constructor() {
    configureOpenApiBase();
  }

  createCase(title: string, ownerTeamId: string): Promise<CreateCaseResponse> {
    return DefaultService.createCase({ requestBody: { title, ownerTeamId } });
  }

  createJdVersion(caseId: string, rawText: string, source: string): Promise<CreateJdVersionResponse> {
    return DefaultService.createJdVersion({ caseId, requestBody: { rawText, source } });
  }

  createKeywordDraft(caseId: string, jdVersionId: string): Promise<CreateKeywordDraftJobResponse> {
    return DefaultService.createKeywordDraftJob({
      caseId,
      requestBody: {
        jdVersionId,
        modelVersion: 'gpt-5.4-mini',
        promptVersion: 'draft-v1',
      },
    });
  }

  confirmPlan(
    planId: string,
    draft: ConditionPlanDraft,
    confirmedBy: string,
  ): Promise<ConfirmConditionPlanResponse> {
    return DefaultService.confirmConditionPlan({
      planId,
      requestBody: { ...draft, confirmedBy },
    });
  }

  createSearchRun(caseId: string, planId: string, pageBudget: number): Promise<CreateSearchRunResponse> {
    return DefaultService.createSearchRun({
      requestBody: {
        caseId,
        planId,
        pageBudget,
        idempotencyKey: `web-${String(Date.now())}`,
      },
    });
  }

  getSearchRun(runId: string): Promise<SearchRunStatusResponse> {
    return DefaultService.getSearchRun({ runId });
  }

  getSearchRunPages(runId: string): Promise<SearchRunPagesResponse> {
    return DefaultService.getSearchRunPages({ runId });
  }

  getCandidate(candidateId: string): Promise<CandidateDetailResponse> {
    return DefaultService.getCaseCandidate({ candidateId });
  }

  saveVerdict(candidateId: string, verdict: Verdict, notes = 'updated in Angular shell') {
    return DefaultService.saveCandidateVerdict({
      candidateId,
      requestBody: {
        verdict,
        reasons: ['manual review'],
        notes,
        actorId: 'consultant-web',
      },
    });
  }

  createExport(caseId: string): Promise<CreateExportResponse> {
    return DefaultService.createExport({
      requestBody: {
        caseId,
        maskPolicy: CreateExportRequest.maskPolicy.MASKED,
        reason: 'weekly shortlist',
        idempotencyKey: `export-${String(Date.now())}`,
      },
    });
  }

  getOpsSummary(): Promise<OpsSummaryResponse> {
    return DefaultService.getOpsSummary();
  }

  getSearchRunTemporalDiagnostic(runId: string): Promise<TemporalSearchRunDiagnosticResponse> {
    return DefaultService.getSearchRunTemporalDiagnostic({ runId });
  }

  createEvalRun(): Promise<CreateEvalRunResponse> {
    return DefaultService.createEvalRun({
      requestBody: {
        suiteId: 'blocking',
        datasetId: 'local-fixture',
        targetVersion: '0.1.0',
      },
    });
  }
}
