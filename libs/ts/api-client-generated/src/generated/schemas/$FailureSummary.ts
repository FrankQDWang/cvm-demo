/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $FailureSummary = {
    properties: {
        searchRuns: {
            type: 'array',
            contains: {
                type: 'SearchRunFailureCount',
            },
            isRequired: true,
        },
    },
} as const;
