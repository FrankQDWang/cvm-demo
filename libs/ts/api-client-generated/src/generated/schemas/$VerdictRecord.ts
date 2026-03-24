/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $VerdictRecord = {
    properties: {
        verdict: {
            type: 'Verdict',
            isRequired: true,
        },
        reasons: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
        notes: {
            type: 'string',
        },
        actorId: {
            type: 'string',
            isRequired: true,
        },
        createdAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
    },
} as const;
