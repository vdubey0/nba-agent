import React from 'react';

const MetricTile = ({ label, value, detail, action }) => (
  <div className="rounded-lg border border-slate-200 bg-white p-4">
    <div className="flex items-start justify-between gap-3">
      <div className="text-sm font-medium text-slate-500">{label}</div>
      {action}
    </div>
    <div className="mt-2 text-2xl font-semibold text-slate-950">{value}</div>
    {detail && <div className="mt-1 text-xs text-slate-500">{detail}</div>}
  </div>
);

export default MetricTile;
