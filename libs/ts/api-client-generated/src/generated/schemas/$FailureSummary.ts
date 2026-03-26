/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $FailureSummary = {
    properties: {
        agentRuns: {
            type: 'array',
            contains: {
                type: 'AgentRunFailureCount',
            },
            isRequired: true,
        },
    },
} as const;
