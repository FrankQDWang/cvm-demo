/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $CreateCaseRequest = {
    properties: {
        title: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
        ownerTeamId: {
            type: 'string',
            isRequired: true,
            minLength: 1,
            pattern: '^[^\\x00]*$',
        },
    },
} as const;
