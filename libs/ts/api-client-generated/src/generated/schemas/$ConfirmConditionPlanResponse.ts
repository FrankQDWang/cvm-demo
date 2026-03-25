/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ConfirmConditionPlanResponse = {
    properties: {
        planId: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        normalizedQuery: {
            type: 'NormalizedQuery',
            isRequired: true,
        },
    },
} as const;
