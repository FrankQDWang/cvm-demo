/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $QueueSummary = {
    properties: {
        searchRuns: {
            type: 'array',
            contains: {
                type: 'SearchRunStatusCount',
            },
            isRequired: true,
        },
    },
} as const;
