/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ConfirmConditionPlanRequest = {
    type: 'all-of',
    contains: [{
        type: 'ConditionPlanDraft',
    }, {
        properties: {
            confirmedBy: {
                type: 'string',
                isRequired: true,
            },
        },
    }],
} as const;
