/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EvidenceRef } from './EvidenceRef';
import type { StructuredFilters } from './StructuredFilters';
export type ConfirmConditionPlanRequest = {
    mustTerms: Array<string>;
    shouldTerms: Array<string>;
    excludeTerms: Array<string>;
    structuredFilters: StructuredFilters;
    evidenceRefs: Array<EvidenceRef>;
    confirmedBy: string;
};

