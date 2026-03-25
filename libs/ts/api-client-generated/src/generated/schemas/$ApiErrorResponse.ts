/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ApiErrorResponse = {
    properties: {
        code: {
            type: 'string',
            isRequired: true,
        },
        message: {
            type: 'string',
            isRequired: true,
        },
        retryable: {
            type: 'boolean',
            isRequired: true,
        },
    },
} as const;
