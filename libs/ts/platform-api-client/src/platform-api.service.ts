import { Injectable } from '@angular/core';

import {
  type AgentRunListResponse,
  type AgentRunResponse,
  type CreateAgentRunRequest,
  type CreateAgentRunResponse,
  DefaultService,
  type OpsSummaryResponse,
  OpenAPI,
  type TemporalAgentRunDiagnosticResponse,
} from '@cvm/api-client-generated';

type RuntimeConfig = {
  apiBaseUrl?: string;
};

let isConfigured = false;

function configureOpenApiBase(): void {
  if (isConfigured) {
    return;
  }
  const runtimeConfig = (globalThis as typeof globalThis & { __CVM_RUNTIME_CONFIG__?: RuntimeConfig }).__CVM_RUNTIME_CONFIG__;
  OpenAPI.BASE = runtimeConfig?.apiBaseUrl ?? 'http://localhost:8010';
  isConfigured = true;
}

@Injectable({ providedIn: 'root' })
export class PlatformApiService {
  constructor() {
    configureOpenApiBase();
  }

  createAgentRun(requestBody: CreateAgentRunRequest): Promise<CreateAgentRunResponse> {
    return DefaultService.createAgentRun({ requestBody });
  }

  getAgentRun(runId: string): Promise<AgentRunResponse> {
    return DefaultService.getAgentRun({ runId });
  }

  listAgentRuns(): Promise<AgentRunListResponse> {
    return DefaultService.listAgentRuns();
  }

  getOpsSummary(): Promise<OpsSummaryResponse> {
    return DefaultService.getOpsSummary();
  }

  getAgentRunTemporalDiagnostic(runId: string): Promise<TemporalAgentRunDiagnosticResponse> {
    return DefaultService.getAgentRunTemporalDiagnostic({ runId });
  }
}
