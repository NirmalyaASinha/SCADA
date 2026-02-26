#!/bin/bash
# Quick SCADA Grid Status Check
# Usage: ./check-grid.sh

set -e

MASTER_URL="http://localhost:9000"
USERNAME="admin"
PASSWORD="scada@2024"

echo "🔐 Authenticating..."
TOKEN=$(curl -s -X POST "$MASTER_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$USERNAME\",\"password\":\"$PASSWORD\"}" | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "❌ Authentication failed!"
  exit 1
fi

echo "✅ Authenticated"
echo ""

# Get grid overview
echo "⚡ GRID STATUS"
echo "=============================================="
GRID=$(curl -s "$MASTER_URL/grid/overview" \
  -H "Authorization: Bearer $TOKEN")

echo "$GRID" | python3 << 'EOF'
import sys, json
data = json.load(sys.stdin)
s = data.get('status', {})
print(f"Frequency        : {s.get('frequency', 0):.3f} Hz")
print(f"Total Generation : {s.get('generation', 0):.1f} MW")
print(f"System Load      : {s.get('load', 0):.1f} MW")
print(f"Transmission Loss: {s.get('transmission_losses', 0):.1f} MW")
print(f"Power Balance    : {s.get('generation', 0) - s.get('load', 0) - s.get('transmission_losses', 0):+.1f} MW")
print(f"Nodes Online     : {s.get('nodes_online', 0)}/{s.get('nodes_total', 15)}")
EOF

echo ""
echo "🔗 NODE STATUS"
echo "=============================================="
curl -s "$MASTER_URL/nodes" \
  -H "Authorization: Bearer $TOKEN" | python3 << 'EOF'
import sys, json
nodes = json.load(sys.stdin)
healthy = 0
print(f"{'ID':<6} {'Name':<12} {'Type':<12} {'Status':<12}")
print("-" * 45)
for n in nodes:
    status = n.get('status', '?')
    icon = "✅" if status == "HEALTHY" else "⚠️"
    if status == "HEALTHY":
        healthy += 1
    print(f"{n.get('node_id', '?'):<6} {n.get('name', '?'):<12} {n.get('node_type', '?'):<12} {icon} {status:<8}")
print("-" * 45)
print(f"Total: {healthy}/{len(nodes)} nodes HEALTHY ✅")
EOF

echo ""
echo "✅ Grid is operational"
