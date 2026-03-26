/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type AgentRuntimeConfigEntry = {
    modelVersion: string;
    thinkingEffort: AgentRuntimeConfigEntry.thinkingEffort;
};
export namespace AgentRuntimeConfigEntry {
    export enum thinkingEffort {
        NONE = 'none',
        MINIMAL = 'minimal',
        LOW = 'low',
        MEDIUM = 'medium',
        HIGH = 'high',
        XHIGH = 'xhigh',
    }
}

