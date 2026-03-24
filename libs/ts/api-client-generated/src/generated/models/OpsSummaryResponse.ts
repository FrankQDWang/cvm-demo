/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { MetricItem } from './MetricItem';
export type OpsSummaryResponse = {
    queue: Record<string, any>;
    failures: Record<string, any>;
    latency: Record<string, any>;
    version: Record<string, any>;
    metrics: Array<MetricItem>;
};

