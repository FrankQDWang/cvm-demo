/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentRunConfig = {
    properties: {
        maxRounds: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
        roundFetchSchedule: {
            type: 'array',
            contains: {
                type: 'number',
                minimum: 1,
            },
            isRequired: true,
        },
        finalTopK: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
    },
} as const;
