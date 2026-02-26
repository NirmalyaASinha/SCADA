import { create } from 'zustand';
import type { AlarmItem } from '../types';

type AlarmsState = {
  alarms: AlarmItem[];
  setAlarms: (alarms: AlarmItem[]) => void;
  addAlarm: (alarm: AlarmItem) => void;
  removeAlarm: (alarmId: string) => void;
};

export const useAlarmsStore = create<AlarmsState>((set) => ({
  alarms: [],
  setAlarms: (alarms) => set({ alarms }),
  addAlarm: (alarm) => set((state) => ({ alarms: [alarm, ...state.alarms] })),
  removeAlarm: (alarmId) => set((state) => ({ alarms: state.alarms.filter((a) => a.id !== alarmId) })),
}));
