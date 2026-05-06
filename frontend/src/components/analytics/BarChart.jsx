import React from 'react';

const BarChart = ({ data, labelKey, valueKey, valueLabel, maxItems = 12 }) => {
  const rows = (data || []).slice(0, maxItems);
  const max = Math.max(...rows.map((row) => Number(row[valueKey]) || 0), 1);

  return (
    <div className="space-y-3">
      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-slate-300 p-6 text-sm text-slate-500">
          No data yet
        </div>
      ) : (
        rows.map((row) => {
          const value = Number(row[valueKey]) || 0;
          const width = `${Math.max((value / max) * 100, 4)}%`;
          return (
            <div key={`${row[labelKey]}-${valueKey}`} className="grid grid-cols-[150px_1fr_90px] items-center gap-3 text-sm">
              <div className="truncate font-medium text-slate-700">{row[labelKey] || 'unknown'}</div>
              <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                <div className="h-full rounded-full bg-cyan-600" style={{ width }} />
              </div>
              <div className="text-right tabular-nums text-slate-600">
                {valueLabel ? valueLabel(value) : value}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
};

export default BarChart;
