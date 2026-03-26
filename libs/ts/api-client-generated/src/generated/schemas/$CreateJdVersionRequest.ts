/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateJdVersionRequest = {
    properties: {
        rawText: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        source: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
    },
} as const;
