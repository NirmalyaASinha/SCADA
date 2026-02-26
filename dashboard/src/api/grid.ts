import apiClient from './client';
import type { GridOverview } from '../types';

export async function fetchGridOverview(): Promise<GridOverview> {
  const response = await apiClient.get<GridOverview>('/grid/overview');
  return response.data;
}
