/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $QueueSummary = {
    properties: {
        agentRuns: {
            type: 'array',
            contains: {
                type: 'AgentRunStatusCount',
            },
            isRequired: true,
        },
    },
} as const;
