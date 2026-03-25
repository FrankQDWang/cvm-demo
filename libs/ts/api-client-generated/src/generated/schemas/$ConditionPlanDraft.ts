/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ConditionPlanDraft = {
    properties: {
        mustTerms: {
            type: 'array',
            contains: {
                type: 'string',
                minLength: 1,
            },
            isRequired: true,
        },
        shouldTerms: {
            type: 'array',
            contains: {
                type: 'string',
                minLength: 1,
            },
            isRequired: true,
        },
        excludeTerms: {
            type: 'array',
            contains: {
                type: 'string',
                minLength: 1,
            },
            isRequired: true,
        },
        structuredFilters: {
            type: 'StructuredFilters',
            isRequired: true,
        },
        evidenceRefs: {
            type: 'array',
            contains: {
                type: 'EvidenceRef',
            },
            isRequired: true,
        },
    },
} as const;
