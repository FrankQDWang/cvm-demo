/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TemporalAgentRunDiagnosticResponse = {
    runId: string;
    workflowId: string;
    namespace: string;
    taskQueue: string;
    appStatus: string;
    currentRound: number;
    stepCount: number;
    finalShortlistCount: number;
    temporalExecutionFound: boolean;
    temporalExecutionStatus?: string | null;
    visibilityIndexed: boolean;
    visibilityBackend: string;
    startedAt?: string | null;
    closedAt?: string | null;
    error?: string | null;
    errorCode?: string | null;
    errorMessage?: string | null;
    stopReason?: string | null;
    langfuseTraceUrl?: string | null;
    temporalUiUrl: string;
};

