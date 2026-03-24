/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $SearchRunPageSnapshot = {
    properties: {
        pageNo: {
            type: 'number',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        fetchedAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
        candidates: {
            type: 'array',
            contains: {
                type: 'CandidateCard',
            },
            isRequired: true,
        },
        total: {
            type: 'number',
            isRequired: true,
        },
        errorCode: {
            type: 'string',
        },
        errorMessage: {
            type: 'string',
        },
    },
} as const;
