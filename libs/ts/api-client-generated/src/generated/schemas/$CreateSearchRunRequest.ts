/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateSearchRunRequest = {
    properties: {
        caseId: {
            type: 'string',
            isRequired: true,
        },
        planId: {
            type: 'string',
            isRequired: true,
        },
        pageBudget: {
            type: 'number',
            isRequired: true,
        },
        idempotencyKey: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
