import { Injectable } from '@angular/core';

import {
  CreateExportRequest,
  DefaultService,
  OpenAPI,
  type ConditionPlanDraft,
  Verdict
} from '@cvm/api-client-generated';

OpenAPI.BASE = 'http://localhost:8000';

@Injectable({ providedIn: 'root' })
export class PlatformApiService {
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
        modelVersion: 'stub-1',
        promptVersion: 'draft-v1'
      }
    });
  }

  confirmPlan(planId: string, draft: ConditionPlanDraft, confirmedBy: string) {
    return DefaultService.confirmConditionPlan({
      planId,
      requestBody: { ...draft, confirmedBy }
    });
  }

  createSearchRun(caseId: string, planId: string) {
    return DefaultService.createSearchRun({
      requestBody: {
        caseId,
        planId,
        pageBudget: 1,
        idempotencyKey: `web-${Date.now()}`
      }
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

  saveVerdict(candidateId: string, verdict: Verdict) {
    return DefaultService.saveCandidateVerdict({
      candidateId,
      requestBody: {
        verdict,
        reasons: ['manual review'],
        notes: 'updated in Angular shell',
        actorId: 'consultant-web'
      }
    });
  }

  createExport(caseId: string) {
    return DefaultService.createExport({
      requestBody: {
        caseId,
        maskPolicy: CreateExportRequest.maskPolicy.MASKED,
        reason: 'weekly shortlist',
        idempotencyKey: `export-${Date.now()}`
      }
    });
  }

  getOpsSummary() {
    return DefaultService.getOpsSummary();
  }

  createEvalRun() {
    return DefaultService.createEvalRun({
      requestBody: {
        suiteId: 'blocking',
        datasetId: 'local-fixture',
        targetVersion: '0.1.0'
      }
    });
  }
}
