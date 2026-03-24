/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CandidateDetailResponse = {
    properties: {
        candidate: {
            type: 'CandidateCard',
            isRequired: true,
        },
        resumeSnapshot: {
            type: 'ResumeSnapshot',
            isRequired: true,
        },
        aiAnalysis: {
            type: 'ResumeAnalysis',
            isRequired: true,
        },
        verdictHistory: {
            type: 'array',
            contains: {
                type: 'VerdictRecord',
            },
            isRequired: true,
        },
    },
} as const;
