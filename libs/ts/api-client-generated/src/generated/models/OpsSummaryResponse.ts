/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { FailureSummary } from './FailureSummary';
import type { LatencySummary } from './LatencySummary';
import type { MetricItem } from './MetricItem';
import type { OpsVersionInfo } from './OpsVersionInfo';
import type { QueueSummary } from './QueueSummary';
export type OpsSummaryResponse = {
    queue: QueueSummary;
    failures: FailureSummary;
    latency: LatencySummary;
    version: OpsVersionInfo;
    metrics: Array<MetricItem>;
};

