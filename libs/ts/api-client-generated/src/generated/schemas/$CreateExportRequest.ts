/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateExportRequest = {
    properties: {
        caseId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        maskPolicy: {
            type: 'Enum',
            isRequired: true,
        },
        reason: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        idempotencyKey: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
    },
} as const;
