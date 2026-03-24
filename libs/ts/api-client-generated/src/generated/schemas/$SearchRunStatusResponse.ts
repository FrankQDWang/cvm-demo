/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $SearchRunStatusResponse = {
    properties: {
        runId: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        progress: {
            type: 'number',
            isRequired: true,
        },
        pageCount: {
            type: 'number',
            isRequired: true,
        },
        errorSummary: {
            type: 'string',
        },
    },
} as const;
