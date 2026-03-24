/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateKeywordDraftJobResponse = {
    properties: {
        jobId: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        planId: {
            type: 'string',
            isRequired: true,
        },
        draft: {
            type: 'ConditionPlanDraft',
            isRequired: true,
        },
    },
} as const;
