/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AgentRunListResponse } from '../models/AgentRunListResponse';
import type { AgentRunResponse } from '../models/AgentRunResponse';
import type { CandidateDetailResponse } from '../models/CandidateDetailResponse';
import type { CreateAgentRunRequest } from '../models/CreateAgentRunRequest';
import type { CreateAgentRunResponse } from '../models/CreateAgentRunResponse';
import type { CreateCaseRequest } from '../models/CreateCaseRequest';
import type { CreateCaseResponse } from '../models/CreateCaseResponse';
import type { CreateEvalRunRequest } from '../models/CreateEvalRunRequest';
import type { CreateEvalRunResponse } from '../models/CreateEvalRunResponse';
import type { CreateExportRequest } from '../models/CreateExportRequest';
import type { CreateExportResponse } from '../models/CreateExportResponse';
import type { CreateJdVersionRequest } from '../models/CreateJdVersionRequest';
import type { CreateJdVersionResponse } from '../models/CreateJdVersionResponse';
import type { OpsSummaryResponse } from '../models/OpsSummaryResponse';
import type { SaveVerdictRequest } from '../models/SaveVerdictRequest';
import type { SaveVerdictResponse } from '../models/SaveVerdictResponse';
import type { TemporalAgentRunDiagnosticResponse } from '../models/TemporalAgentRunDiagnosticResponse';
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
            errors: {
                400: `Invalid input or contract validation failure.`,
            },
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
            errors: {
                400: `Invalid input or contract validation failure.`,
                404: `Requested resource was not found.`,
            },
        });
    }
    /**
     * Create an agent run
     * @returns CreateAgentRunResponse Agent run created
     * @throws ApiError
     */
    public static createAgentRun({
        requestBody,
    }: {
        requestBody: CreateAgentRunRequest,
    }): CancelablePromise<CreateAgentRunResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/api/v1/agent-runs',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Invalid input or contract validation failure.`,
                409: `The current resource state does not allow this operation.`,
                503: `A required upstream dependency is temporarily unavailable or retryable.`,
            },
        });
    }
    /**
     * List agent runs
     * @returns AgentRunListResponse Agent runs
     * @throws ApiError
     */
    public static listAgentRuns(): CancelablePromise<AgentRunListResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/agent-runs',
        });
    }
    /**
     * Get agent run status and result
     * @returns AgentRunResponse Agent run status and result
     * @throws ApiError
     */
    public static getAgentRun({
        runId,
    }: {
        runId: string,
    }): CancelablePromise<AgentRunResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/agent-runs/{runId}',
            path: {
                'runId': runId,
            },
            errors: {
                404: `Requested resource was not found.`,
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
            errors: {
                404: `Requested resource was not found.`,
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
            errors: {
                400: `Invalid input or contract validation failure.`,
                404: `Requested resource was not found.`,
            },
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
            errors: {
                400: `Invalid input or contract validation failure.`,
                403: `The caller is not allowed to perform this operation.`,
                404: `Requested resource was not found.`,
                502: `A required upstream dependency returned a non-retryable failure.`,
            },
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
     * Get Temporal diagnostic for an agent run
     * @returns TemporalAgentRunDiagnosticResponse Temporal agent run diagnostic
     * @throws ApiError
     */
    public static getAgentRunTemporalDiagnostic({
        runId,
    }: {
        runId: string,
    }): CancelablePromise<TemporalAgentRunDiagnosticResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/api/v1/ops/temporal/agent-runs/{runId}',
            path: {
                'runId': runId,
            },
            errors: {
                404: `Requested resource was not found.`,
                503: `A required upstream dependency is temporarily unavailable or retryable.`,
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
            errors: {
                400: `Invalid input or contract validation failure.`,
            },
        });
    }
}
