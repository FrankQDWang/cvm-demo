/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateSearchRunRequest = {
    properties: {
        caseId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
        },
        planId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
        },
        pageBudget: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
        idempotencyKey: {
            type: 'string',
            isRequired: true,
            minLength: 1,
        },
    },
} as const;
