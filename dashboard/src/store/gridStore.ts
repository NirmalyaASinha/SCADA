import { create } from 'zustand';
import type { GridOverview } from '../types';

type GridState = {
  overview: GridOverview | null;
  status: 'connecting' | 'online' | 'offline';
  setOverview: (overview: GridOverview) => void;
  setStatus: (status: GridState['status']) => void;
};

export const useGridStore = create<GridState>((set) => ({
  overview: null,
  status: 'connecting',
  setOverview: (overview) => set({ overview, status: 'online' }),
  setStatus: (status) => set({ status }),
}));
