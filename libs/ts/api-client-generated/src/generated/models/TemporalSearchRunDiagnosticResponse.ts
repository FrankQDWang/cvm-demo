/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type TemporalSearchRunDiagnosticResponse = {
    runId: string;
    workflowId: string;
    namespace: string;
    taskQueue: string;
    appStatus: string;
    temporalExecutionFound: boolean;
    temporalExecutionStatus?: string | null;
    visibilityIndexed: boolean;
    visibilityBackend: string;
    startedAt?: string | null;
    closedAt?: string | null;
    error?: string | null;
    temporalUiUrl: string;
};

