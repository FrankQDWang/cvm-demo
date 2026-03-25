/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Verdict } from './Verdict';
export type SaveVerdictRequest = {
    verdict: Verdict;
    reasons: Array<string>;
    notes?: string;
    actorId: string;
    resumeSnapshotId?: string | null;
};

