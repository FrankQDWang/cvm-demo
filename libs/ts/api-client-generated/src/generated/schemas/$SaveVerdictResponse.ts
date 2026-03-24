/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $SaveVerdictResponse = {
    properties: {
        candidateId: {
            type: 'string',
            isRequired: true,
        },
        latestVerdict: {
            type: 'Verdict',
            isRequired: true,
        },
        updatedAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
    },
} as const;
