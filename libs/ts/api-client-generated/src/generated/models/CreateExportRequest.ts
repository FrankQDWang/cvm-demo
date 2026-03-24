/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type CreateExportRequest = {
    caseId: string;
    maskPolicy: CreateExportRequest.maskPolicy;
    reason: string;
    idempotencyKey: string;
};
export namespace CreateExportRequest {
    export enum maskPolicy {
        MASKED = 'masked',
        SENSITIVE = 'sensitive',
    }
}

