// Grid Store
import { create } from 'zustand';

const useGridStore = create((set) => ({
  gridState: null,
  topology: null,
  systemFrequency: 50.0,
  
  setGridState: (state) => set({ 
    gridState: state,
    systemFrequency: state.system_frequency_hz || 50.0
  }),
  
  setTopology: (topology) => set({ topology }),
  
  updateFrequency: (frequency) => set({ systemFrequency: frequency }),
}));

export default useGridStore;
