// Security Store
import { create } from 'zustand';

const useSecurityStore = create((set) => ({
  unknownConnections: [],
  securityEvents: [],
  
  addUnknownConnection: (connection) => set((state) => ({
    unknownConnections: [connection, ...state.unknownConnections],
  })),
  
  removeUnknownConnection: (connectionId) => set((state) => ({
    unknownConnections: state.unknownConnections.filter(c => c.id !== connectionId),
  })),
  
  addSecurityEvent: (event) => set((state) => ({
    securityEvents: [event, ...state.securityEvents].slice(0, 1000), // Keep last 1000
  })),
  
  clearEvents: () => set({ securityEvents: [] }),
}));

export default useSecurityStore;
