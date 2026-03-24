/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateExportRequest = {
    properties: {
        caseId: {
            type: 'string',
            isRequired: true,
        },
        maskPolicy: {
            type: 'Enum',
            isRequired: true,
        },
        reason: {
            type: 'string',
            isRequired: true,
        },
        idempotencyKey: {
            type: 'string',
            isRequired: true,
        },
    },
} as const;
