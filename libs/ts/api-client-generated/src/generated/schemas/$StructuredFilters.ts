/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $StructuredFilters = {
    properties: {
        page: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
        pageSize: {
            type: 'number',
            isRequired: true,
            minimum: 1,
        },
        location: {
            type: 'array',
            contains: {
                type: 'string',
                minLength: 1,
            },
        },
        degree: {
            type: 'number',
        },
        schoolType: {
            type: 'number',
        },
        workExperienceRange: {
            type: 'number',
        },
        position: {
            type: 'string',
            minLength: 1,
        },
        workContent: {
            type: 'string',
            minLength: 1,
        },
        company: {
            type: 'string',
            minLength: 1,
        },
        school: {
            type: 'string',
            minLength: 1,
        },
    },
} as const;
