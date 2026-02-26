export const topologyPositions: Record<string, { x: number; y: number; row: number }>
  = {
  'GEN-001': { x: 50, y: 40, row: 1 },
  'GEN-002': { x: 260, y: 40, row: 1 },
  'GEN-003': { x: 470, y: 40, row: 1 },
  'SUB-001': { x: 10, y: 180, row: 2 },
  'SUB-002': { x: 120, y: 180, row: 2 },
  'SUB-003': { x: 230, y: 180, row: 2 },
  'SUB-004': { x: 340, y: 180, row: 2 },
  'SUB-005': { x: 450, y: 180, row: 2 },
  'SUB-006': { x: 560, y: 180, row: 2 },
  'SUB-007': { x: 670, y: 180, row: 2 },
  'DIST-001': { x: 40, y: 320, row: 3 },
  'DIST-002': { x: 190, y: 320, row: 3 },
  'DIST-003': { x: 340, y: 320, row: 3 },
  'DIST-004': { x: 490, y: 320, row: 3 },
  'DIST-005': { x: 640, y: 320, row: 3 },
};

export const topologyEdges = [
  ['GEN-001', 'SUB-002'],
  ['GEN-002', 'SUB-004'],
  ['GEN-003', 'SUB-006'],
  ['SUB-001', 'DIST-001'],
  ['SUB-002', 'DIST-002'],
  ['SUB-003', 'DIST-002'],
  ['SUB-004', 'DIST-003'],
  ['SUB-005', 'DIST-004'],
  ['SUB-006', 'DIST-004'],
  ['SUB-007', 'DIST-005'],
];
