/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $OpsSummaryResponse = {
    properties: {
        queue: {
            type: 'QueueSummary',
            isRequired: true,
        },
        failures: {
            type: 'FailureSummary',
            isRequired: true,
        },
        latency: {
            type: 'LatencySummary',
            isRequired: true,
        },
        version: {
            type: 'OpsVersionInfo',
            isRequired: true,
        },
        metrics: {
            type: 'array',
            contains: {
                type: 'MetricItem',
            },
            isRequired: true,
        },
    },
} as const;
