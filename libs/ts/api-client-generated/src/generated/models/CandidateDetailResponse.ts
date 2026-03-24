/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CandidateCard } from './CandidateCard';
import type { ResumeAnalysis } from './ResumeAnalysis';
import type { ResumeSnapshot } from './ResumeSnapshot';
import type { VerdictRecord } from './VerdictRecord';
export type CandidateDetailResponse = {
    candidate: CandidateCard;
    resumeSnapshot: ResumeSnapshot;
    aiAnalysis: ResumeAnalysis;
    verdictHistory: Array<VerdictRecord>;
};

