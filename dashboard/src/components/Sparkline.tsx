export default function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) {
    return <span className="text-gray-600">-</span>;
  }

  const width = 80;
  const height = 20;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1 || 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height}>
      <polyline
        fill="none"
        stroke="#00ff88"
        strokeWidth="1"
        points={points}
      />
    </svg>
  );
}
