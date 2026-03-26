/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $AgentShortlistCandidate = {
    properties: {
        externalIdentityId: {
            type: 'string',
            isRequired: true,
        },
        name: {
            type: 'string',
            isRequired: true,
        },
        title: {
            type: 'string',
            isRequired: true,
        },
        company: {
            type: 'string',
            isRequired: true,
        },
        location: {
            type: 'string',
            isRequired: true,
        },
        summary: {
            type: 'string',
            isRequired: true,
        },
        reason: {
            type: 'string',
            isRequired: true,
        },
        score: {
            type: 'number',
            isRequired: true,
        },
        sourceRound: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
    },
} as const;
