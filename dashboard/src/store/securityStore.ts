import { create } from 'zustand';
import type { SecurityConnection } from '../types';

type SecurityState = {
  connections: SecurityConnection[];
  unknownCount: number;
  setConnections: (connections: SecurityConnection[]) => void;
  addUnknown: (connection: SecurityConnection) => void;
};

export const useSecurityStore = create<SecurityState>((set) => ({
  connections: [],
  unknownCount: 0,
  setConnections: (connections) =>
    set({
      connections,
      unknownCount: connections.filter((c) => c.status === 'UNKNOWN').length,
    }),
  addUnknown: (connection) =>
    set((state) => ({
      connections: [connection, ...state.connections],
      unknownCount: state.unknownCount + 1,
    })),
}));
