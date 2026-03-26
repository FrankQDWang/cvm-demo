/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentRunListItem = {
    properties: {
        runId: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        currentRound: {
            type: 'number',
            isRequired: true,
        },
        createdAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
        finishedAt: {
            type: 'string',
            isNullable: true,
            format: 'date-time',
        },
        errorCode: {
            type: 'string',
            isNullable: true,
        },
        errorMessage: {
            type: 'string',
            isNullable: true,
        },
        langfuseTraceUrl: {
            type: 'string',
            isNullable: true,
        },
    },
} as const;
