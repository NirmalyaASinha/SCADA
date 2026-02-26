// Alarms Store
import { create } from 'zustand';

const useAlarmsStore = create((set) => ({
  alarms: [],
  criticalCount: 0,
  highCount: 0,
  mediumCount: 0,
  lowCount: 0,
  
  setAlarms: (alarms) => {
    const critical = alarms.filter(a => a.priority === 'critical').length;
    const high = alarms.filter(a => a.priority === 'high').length;
    const medium = alarms.filter(a => a.priority === 'medium').length;
    const low = alarms.filter(a => a.priority === 'low').length;
    
    set({
      alarms,
      criticalCount: critical,
      highCount: high,
      mediumCount: medium,
      lowCount: low,
    });
  },
  
  addAlarm: (alarm) => set((state) => ({
    alarms: [alarm, ...state.alarms],
  })),
  
  removeAlarm: (alarmId) => set((state) => ({
    alarms: state.alarms.filter(a => a.id !== alarmId),
  })),
}));

export default useAlarmsStore;
