/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateEvalRunRequest = {
    properties: {
        suiteId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        datasetId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        targetVersion: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
    },
} as const;
