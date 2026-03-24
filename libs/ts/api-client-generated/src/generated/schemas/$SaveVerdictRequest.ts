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
        },
        actorId: {
            type: 'string',
            isRequired: true,
        },
        resumeSnapshotId: {
            type: 'string',
        },
    },
} as const;
