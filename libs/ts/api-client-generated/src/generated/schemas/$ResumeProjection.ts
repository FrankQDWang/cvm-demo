/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export const $ResumeProjection = {
    properties: {
        workYear: {
            type: 'number',
            isRequired: true,
            isNullable: true,
        },
        currentLocation: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        expectedLocation: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        jobState: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        expectedSalary: {
            type: 'string',
            isRequired: true,
            isNullable: true,
        },
        age: {
            type: 'number',
            isRequired: true,
            isNullable: true,
        },
        education: {
            type: 'array',
            contains: {
                type: 'ResumeEducationItem',
            },
            isRequired: true,
        },
        workExperience: {
            type: 'array',
            contains: {
                type: 'ResumeWorkExperienceItem',
            },
            isRequired: true,
        },
        workSummaries: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
        projectNames: {
            type: 'array',
            contains: {
                type: 'string',
            },
            isRequired: true,
        },
    },
} as const;
