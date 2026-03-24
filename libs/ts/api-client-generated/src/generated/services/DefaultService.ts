/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CandidateDetailResponse } from '../models/CandidateDetailResponse';
import type { ConfirmConditionPlanRequest } from '../models/ConfirmConditionPlanRequest';
import type { ConfirmConditionPlanResponse } from '../models/ConfirmConditionPlanResponse';
import type { CreateCaseRequest } from '../models/CreateCaseRequest';
import type { CreateCaseResponse } from '../models/CreateCaseResponse';
import type { CreateEvalRunRequest } from '../models/CreateEvalRunRequest';
import type { CreateEvalRunResponse } from '../models/CreateEvalRunResponse';
import type { CreateExportRequest } from '../models/CreateExportRequest';
import type { CreateExportResponse } from '../models/CreateExportResponse';
import type { CreateJdVersionRequest } from '../models/CreateJdVersionRequest';
import type { CreateJdVersionResponse } from '../models/CreateJdVersionResponse';
import type { CreateKeywordDraftJobRequest } from '../models/CreateKeywordDraftJobRequest';
import type { CreateKeywordDraftJobResponse } from '../models/CreateKeywordDraftJobResponse';
import type { CreateSearchRunRequest } from '../models/CreateSearchRunRequest';
import type { CreateSearchRunResponse } from '../models/CreateSearchRunResponse';
import type { OpsSummaryResponse } from '../models/OpsSummaryResponse';
import type { SaveVerdictRequest } from '../models/SaveVerdictRequest';
import type { SaveVerdictResponse } from '../models/SaveVerdictResponse';
import type { SearchRunPagesResponse } from '../models/SearchRunPagesResponse';
import type { SearchRunStatusResponse } from '../models/SearchRunStatusResponse';
import type { TemporalSearchRunDiagnosticResponse } from '../models/TemporalSearchRunDiagnosticResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
    /**
     * Create a JD case
     * @returns CreateCaseResponse Case created
     * @throws ApiError
     */
    public static createCase({
        requestBody,
    }: {
        requestBody: CreateCaseRequest,
    }): CancelablePromise<CreateCaseResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/cases',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Create a JD version
     * @returns CreateJdVersionResponse JD version created
     * @throws ApiError
     */
    public static createJdVersion({
        caseId,
        requestBody,
    }: {
        caseId: string,
        requestBody: CreateJdVersionRequest,
    }): CancelablePromise<CreateJdVersionResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/cases/{caseId}/jd-versions',
            path: {
                'caseId': caseId,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Create a keyword draft
     * @returns CreateKeywordDraftJobResponse Draft created
     * @throws ApiError
     */
    public static createKeywordDraftJob({
        caseId,
        requestBody,
    }: {
        caseId: string,
        requestBody: CreateKeywordDraftJobRequest,
    }): CancelablePromise<CreateKeywordDraftJobResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/cases/{caseId}/keyword-draft-jobs',
            path: {
                'caseId': caseId,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Confirm a condition plan
     * @returns ConfirmConditionPlanResponse Plan confirmed
     * @throws ApiError
     */
    public static confirmConditionPlan({
        planId,
        requestBody,
    }: {
        planId: string,
        requestBody: ConfirmConditionPlanRequest,
    }): CancelablePromise<ConfirmConditionPlanResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/condition-plans/{planId}:confirm',
            path: {
                'planId': planId,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Create a search run
     * @returns CreateSearchRunResponse Search run created
     * @throws ApiError
     */
    public static createSearchRun({
        requestBody,
    }: {
        requestBody: CreateSearchRunRequest,
    }): CancelablePromise<CreateSearchRunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/search-runs',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Get search run status
     * @returns SearchRunStatusResponse Search run status
     * @throws ApiError
     */
    public static getSearchRun({
        runId,
    }: {
        runId: string,
    }): CancelablePromise<SearchRunStatusResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/search-runs/{runId}',
            path: {
                'runId': runId,
            },
        });
    }
    /**
     * Get search run pages
     * @returns SearchRunPagesResponse Page snapshots
     * @throws ApiError
     */
    public static getSearchRunPages({
        runId,
        pageNo,
    }: {
        runId: string,
        pageNo?: number,
    }): CancelablePromise<SearchRunPagesResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/search-runs/{runId}/pages',
            path: {
                'runId': runId,
            },
            query: {
                'pageNo': pageNo,
            },
        });
    }
    /**
     * Get candidate detail
     * @returns CandidateDetailResponse Candidate detail
     * @throws ApiError
     */
    public static getCaseCandidate({
        candidateId,
    }: {
        candidateId: string,
    }): CancelablePromise<CandidateDetailResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/case-candidates/{candidateId}',
            path: {
                'candidateId': candidateId,
            },
        });
    }
    /**
     * Save a candidate verdict
     * @returns SaveVerdictResponse Verdict saved
     * @throws ApiError
     */
    public static saveCandidateVerdict({
        candidateId,
        requestBody,
    }: {
        candidateId: string,
        requestBody: SaveVerdictRequest,
    }): CancelablePromise<SaveVerdictResponse> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/api/v1/case-candidates/{candidateId}/verdict',
            path: {
                'candidateId': candidateId,
            },
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Create an export job
     * @returns CreateExportResponse Export job created
     * @throws ApiError
     */
    public static createExport({
        requestBody,
    }: {
        requestBody: CreateExportRequest,
    }): CancelablePromise<CreateExportResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/exports',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
    /**
     * Get ops summary
     * @returns OpsSummaryResponse Ops summary
     * @throws ApiError
     */
    public static getOpsSummary(): CancelablePromise<OpsSummaryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/ops/summary',
        });
    }
    /**
     * Get Temporal diagnostic for a search run
     * @returns TemporalSearchRunDiagnosticResponse Temporal search run diagnostic
     * @throws ApiError
     */
    public static getSearchRunTemporalDiagnostic({
        runId,
    }: {
        runId: string,
    }): CancelablePromise<TemporalSearchRunDiagnosticResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/ops/temporal/search-runs/{runId}',
            path: {
                'runId': runId,
            },
        });
    }
    /**
     * Create an eval run
     * @returns CreateEvalRunResponse Eval run created
     * @throws ApiError
     */
    public static createEvalRun({
        requestBody,
    }: {
        requestBody: CreateEvalRunRequest,
    }): CancelablePromise<CreateEvalRunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/evals/runs',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
}
