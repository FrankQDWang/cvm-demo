/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { StructuredFilters } from './StructuredFilters';
export type NormalizedQuery = {
    jd: string;
    mustTerms: Array<string>;
    shouldTerms: Array<string>;
    excludeTerms: Array<string>;
    structuredFilters: StructuredFilters;
    keyword: string;
};

