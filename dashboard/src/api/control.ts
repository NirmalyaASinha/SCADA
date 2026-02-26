import apiClient from './client';

export type SelectResponse = {
  session_id: string;
  expires_at: string;
  time_remaining_s: number;
  message: string;
};

export type OperateResponse = {
  result: string;
  response_time_ms: number;
  message: string;
  new_breaker_state: string;
};

export async function selectBreaker(payload: {
  node_id: string;
  breaker_id: string;
  action: 'open' | 'close';
  operator_id: string;
  reason: string;
}): Promise<SelectResponse> {
  const response = await apiClient.post<SelectResponse>('/control/breaker/select', payload);
  return response.data;
}

export async function operateBreaker(payload: {
  session_id: string;
  operator_id: string;
}): Promise<OperateResponse> {
  const response = await apiClient.post<OperateResponse>('/control/breaker/operate', payload);
  return response.data;
}

export async function cancelBreaker(payload: { session_id: string }): Promise<void> {
  await apiClient.post('/control/breaker/cancel', payload);
}
