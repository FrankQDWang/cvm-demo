/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentRunResponse = {
    properties: {
        runId: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        jdText: {
            type: 'string',
            isRequired: true,
        },
        sourcingPreferenceText: {
            type: 'string',
            isRequired: true,
        },
        config: {
            type: 'AgentRunConfig',
            isRequired: true,
        },
        currentRound: {
            type: 'number',
            isRequired: true,
        },
        modelVersion: {
            type: 'string',
            isRequired: true,
        },
        promptVersion: {
            type: 'string',
            isRequired: true,
        },
        workflowId: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        temporalNamespace: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        temporalTaskQueue: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        langfuseTraceId: {
            type: 'string',
            isNullable: true,
        },
        langfuseTraceUrl: {
            type: 'string',
            isNullable: true,
        },
        steps: {
            type: 'array',
            contains: {
                type: 'AgentRunStep',
            },
            isRequired: true,
        },
        finalShortlist: {
            type: 'array',
            contains: {
                type: 'AgentShortlistCandidate',
            },
            isRequired: true,
        },
        seenResumeIds: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
        errorCode: {
            type: 'string',
            isNullable: true,
        },
        errorMessage: {
            type: 'string',
            isNullable: true,
        },
        createdAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
        startedAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
        finishedAt: {
            type: 'string',
            isNullable: true,
            format: 'date-time',
        },
    },
} as const;
