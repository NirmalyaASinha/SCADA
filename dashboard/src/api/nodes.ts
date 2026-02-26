import apiClient from './client';
import type { NodeInfo } from '../types';

export async function fetchNodes(): Promise<NodeInfo[]> {
  const response = await apiClient.get<{ nodes: NodeInfo[] }>('/nodes');
  return response.data.nodes;
}

export async function fetchNodeDetail(nodeId: string): Promise<NodeInfo> {
  const response = await apiClient.get<NodeInfo>(`/nodes/${nodeId}`);
  return response.data;
}

export async function fetchNodeTelemetry(nodeId: string): Promise<Record<string, number | string | boolean | null>> {
  const response = await apiClient.get<{ telemetry: Record<string, number | string | boolean | null> }>(`/nodes/${nodeId}/telemetry`);
  return response.data.telemetry;
}

export async function fetchNodeConnections(nodeId: string): Promise<{ connections: Array<Record<string, unknown>> }> {
  const response = await apiClient.get<{ connections: Array<Record<string, unknown>> }>(`/nodes/${nodeId}/connections`);
  return response.data;
}
