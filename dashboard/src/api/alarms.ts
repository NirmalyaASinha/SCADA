import apiClient from './client';
import type { AlarmItem } from '../types';

export async function fetchActiveAlarms(): Promise<AlarmItem[]> {
  const response = await apiClient.get<{ alarms: AlarmItem[] }>('/alarms/active');
  return response.data.alarms;
}

export async function acknowledgeAlarm(alarmId: string, operatorId: string, comment: string): Promise<void> {
  await apiClient.post(`/alarms/${alarmId}/acknowledge`, {
    operator_id: operatorId,
    comment,
  });
}
