/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ResumeAnalysis = {
    properties: {
        status: {
            type: 'string',
            isRequired: true,
        },
        summary: {
            type: 'string',
            isRequired: true,
        },
        evidenceSpans: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
        riskFlags: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
    },
} as const;
