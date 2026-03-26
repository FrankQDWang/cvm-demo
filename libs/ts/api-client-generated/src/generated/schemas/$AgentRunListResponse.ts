/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentRunListResponse = {
    properties: {
        runs: {
            type: 'array',
            contains: {
                type: 'AgentRunListItem',
            },
            isRequired: true,
        },
    },
} as const;
