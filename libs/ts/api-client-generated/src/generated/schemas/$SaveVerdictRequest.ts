/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $SaveVerdictRequest = {
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
            pattern: '^[^\\x00]*$',
        },
        actorId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        resumeSnapshotId: {
            type: 'string',
            isNullable: true,
            pattern: '^[^\\x00]*$',
        },
    },
} as const;
