/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $TemporalSearchRunDiagnosticResponse = {
    properties: {
        runId: {
            type: 'string',
            isRequired: true,
        },
        workflowId: {
            type: 'string',
            isRequired: true,
        },
        namespace: {
            type: 'string',
            isRequired: true,
        },
        taskQueue: {
            type: 'string',
            isRequired: true,
        },
        appStatus: {
            type: 'string',
            isRequired: true,
        },
        temporalExecutionFound: {
            type: 'boolean',
            isRequired: true,
        },
        temporalExecutionStatus: {
            type: 'string',
            isNullable: true,
        },
        visibilityIndexed: {
            type: 'boolean',
            isRequired: true,
        },
        visibilityBackend: {
            type: 'string',
            isRequired: true,
        },
        startedAt: {
            type: 'string',
            isNullable: true,
            format: 'date-time',
        },
        closedAt: {
            type: 'string',
            isNullable: true,
            format: 'date-time',
        },
        error: {
            type: 'string',
            isNullable: true,
        },
        temporalUiUrl: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
