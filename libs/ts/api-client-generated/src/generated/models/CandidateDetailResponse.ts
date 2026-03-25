/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CandidateCard } from './CandidateCard';
import type { CandidateResumeView } from './CandidateResumeView';
import type { ResumeAnalysis } from './ResumeAnalysis';
import type { VerdictRecord } from './VerdictRecord';
export type CandidateDetailResponse = {
    candidate: CandidateCard;
    resumeView: CandidateResumeView;
    aiAnalysis: ResumeAnalysis;
    verdictHistory: Array<VerdictRecord>;
};

