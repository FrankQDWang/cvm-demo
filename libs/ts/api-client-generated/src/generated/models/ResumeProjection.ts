/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ResumeEducationItem } from './ResumeEducationItem';
import type { ResumeWorkExperienceItem } from './ResumeWorkExperienceItem';
export type ResumeProjection = {
    workYear: number | null;
    currentLocation: string | null;
    expectedLocation: string | null;
    jobState: string | null;
    expectedSalary: string | null;
    age: number | null;
    education: Array<ResumeEducationItem>;
    workExperience: Array<ResumeWorkExperienceItem>;
    workSummaries: Array<string>;
    projectNames: Array<string>;
};

