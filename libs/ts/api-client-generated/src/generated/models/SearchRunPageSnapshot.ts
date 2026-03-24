/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CandidateCard } from './CandidateCard';
export type SearchRunPageSnapshot = {
    pageNo: number;
    status: string;
    fetchedAt: string;
    candidates: Array<CandidateCard>;
    total: number;
    errorCode?: string;
    errorMessage?: string;
};

