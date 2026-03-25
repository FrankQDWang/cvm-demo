/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $NormalizedQuery = {
    properties: {
        jd: {
            type: 'string',
            isRequired: true,
            minLength: 1,
        },
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
        keyword: {
            type: 'string',
            isRequired: true,
            minLength: 1,
        },
    },
} as const;
