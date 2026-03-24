import { Injectable } from '@angular/core';

import {
  CreateExportRequest,
  DefaultService,
  OpenAPI,
  type ConditionPlanDraft,
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

  createCase(title: string, ownerTeamId: string) {
    return DefaultService.createCase({ requestBody: { title, ownerTeamId } });
  }

  createJdVersion(caseId: string, rawText: string, source: string) {
    return DefaultService.createJdVersion({ caseId, requestBody: { rawText, source } });
  }

  createKeywordDraft(caseId: string, jdVersionId: string) {
    return DefaultService.createKeywordDraftJob({
      caseId,
      requestBody: {
        jdVersionId,
        modelVersion: 'gpt-5.4-mini',
        promptVersion: 'draft-v1',
      },
    });
  }

  confirmPlan(planId: string, draft: ConditionPlanDraft, confirmedBy: string) {
    return DefaultService.confirmConditionPlan({
      planId,
      requestBody: { ...draft, confirmedBy },
    });
  }

  createSearchRun(caseId: string, planId: string, pageBudget: number) {
    return DefaultService.createSearchRun({
      requestBody: {
        caseId,
        planId,
        pageBudget,
        idempotencyKey: `web-${Date.now()}`,
      },
    });
  }

  getSearchRun(runId: string) {
    return DefaultService.getSearchRun({ runId });
  }

  getSearchRunPages(runId: string) {
    return DefaultService.getSearchRunPages({ runId });
  }

  getCandidate(candidateId: string) {
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

  createExport(caseId: string) {
    return DefaultService.createExport({
      requestBody: {
        caseId,
        maskPolicy: CreateExportRequest.maskPolicy.MASKED,
        reason: 'weekly shortlist',
        idempotencyKey: `export-${Date.now()}`,
      },
    });
  }

  getOpsSummary() {
    return DefaultService.getOpsSummary();
  }

  getSearchRunTemporalDiagnostic(runId: string) {
    return DefaultService.getSearchRunTemporalDiagnostic({ runId });
  }

  createEvalRun() {
    return DefaultService.createEvalRun({
      requestBody: {
        suiteId: 'blocking',
        datasetId: 'local-fixture',
        targetVersion: '0.1.0',
      },
    });
  }
}
