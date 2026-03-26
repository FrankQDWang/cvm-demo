/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentRunStep = {
    properties: {
        stepNo: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
        roundNo: {
            type: 'number',
            isNullable: true,
            minimum: 1,
        },
        stepType: {
            type: 'string',
            isRequired: true,
        },
        title: {
            type: 'string',
            isRequired: true,
        },
        status: {
            type: 'string',
            isRequired: true,
        },
        summary: {
            type: 'string',
            isRequired: true,
        },
        payload: {
            type: 'dictionary',
            contains: {
                properties: {
                },
            },
            isRequired: true,
        },
        occurredAt: {
            type: 'string',
            isRequired: true,
            format: 'date-time',
        },
    },
} as const;
