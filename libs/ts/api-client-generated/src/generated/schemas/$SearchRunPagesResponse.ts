/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $SearchRunPagesResponse = {
    properties: {
        runId: {
            type: 'string',
            isRequired: true,
        },
        snapshots: {
            type: 'array',
            contains: {
                type: 'SearchRunPageSnapshot',
            },
            isRequired: true,
        },
    },
} as const;
