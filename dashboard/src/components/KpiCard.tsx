import FlashValue from './FlashValue';

export default function KpiCard({
  label,
  value,
  unit,
  statusClass,
}: {
  label: string;
  value: number;
  unit?: string;
  statusClass?: string;
}) {
  return (
    <div className="panel p-4 flex flex-col gap-2">
      <div className="text-xs uppercase tracking-widest text-gray-400">{label}</div>
      <div className={`text-2xl font-mono ${statusClass || ''}`}>
        <FlashValue
          value={value}
          formatter={(val) => `${Number(val).toFixed(2)}${unit ? ` ${unit}` : ''}`}
        />
      </div>
    </div>
  );
}
