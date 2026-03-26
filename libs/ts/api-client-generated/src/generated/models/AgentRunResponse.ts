/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AgentRunConfig } from './AgentRunConfig';
import type { AgentRunStep } from './AgentRunStep';
import type { AgentShortlistCandidate } from './AgentShortlistCandidate';
export type AgentRunResponse = {
    runId: string;
    status: string;
    jdText: string;
    sourcingPreferenceText: string;
    config: AgentRunConfig;
    currentRound: number;
    modelVersion: string;
    promptVersion: string;
    workflowId: string | null;
    temporalNamespace: string | null;
    temporalTaskQueue: string | null;
    langfuseTraceId?: string | null;
    langfuseTraceUrl?: string | null;
    steps: Array<AgentRunStep>;
    finalShortlist: Array<AgentShortlistCandidate>;
    seenResumeIds: Array<string>;
    errorCode?: string | null;
    errorMessage?: string | null;
    createdAt: string;
    startedAt: string;
    finishedAt?: string | null;
};

