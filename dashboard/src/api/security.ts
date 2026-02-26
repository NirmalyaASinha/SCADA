import apiClient from './client';
import type { SecurityConnection } from '../types';

export type SecurityOverview = {
  total_connections: number;
  authorised: number;
  unknown: number;
  by_node: Array<{ node_id: string; connections: SecurityConnection[] }>;
};

export async function fetchSecurityConnections(): Promise<SecurityOverview> {
  const response = await apiClient.get<SecurityOverview>('/security/connections');
  return response.data;
}
