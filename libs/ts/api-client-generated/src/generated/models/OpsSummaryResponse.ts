/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MetricItem } from './MetricItem';
import type { OpsVersionInfo } from './OpsVersionInfo';
export type OpsSummaryResponse = {
    queue: Record<string, any>;
    failures: Record<string, any>;
    latency: Record<string, any>;
    version: OpsVersionInfo;
    metrics: Array<MetricItem>;
};

