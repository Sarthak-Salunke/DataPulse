import React from 'react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

interface ChartRendererProps {
  type: 'bar_chart' | 'line_chart';
  rows: Record<string, unknown>[];
  columns: string[];
}

const AXIS_STYLE = {
  fontFamily: 'var(--font-mono)',
  fontSize: 10,
  fill: 'var(--text-muted)',
} as const;

const TOOLTIP_STYLE = {
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border)',
  borderRadius: '6px',
  fontSize: '11px',
  fontFamily: 'var(--font-mono)',
} as const;

const ChartRenderer: React.FC<ChartRendererProps> = ({ type, rows, columns }) => {
  if (!rows.length || columns.length < 2) return null;

  const xKey = columns[0];
  const yKey = columns[1];

  const data = rows.map((row) => ({
    [xKey]: String(row[xKey] ?? ''),
    [yKey]: Number(row[yKey] ?? 0),
  }));

  const sharedProps = {
    data,
    margin: { top: 8, right: 8, left: 0, bottom: 44 },
  };

  return (
    <div style={{ width: '100%', height: 220, marginTop: '10px' }}>
      <ResponsiveContainer width="100%" height="100%">
        {type === 'bar_chart' ? (
          <BarChart {...sharedProps}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.06)"
            />
            <XAxis
              dataKey={xKey}
              tick={AXIS_STYLE}
              angle={-30}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={AXIS_STYLE} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Bar dataKey={yKey} fill="var(--cyan)" radius={[3, 3, 0, 0]} />
          </BarChart>
        ) : (
          <LineChart {...sharedProps}>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.06)"
            />
            <XAxis
              dataKey={xKey}
              tick={AXIS_STYLE}
              angle={-30}
              textAnchor="end"
              interval={0}
            />
            <YAxis tick={AXIS_STYLE} />
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Line
              type="monotone"
              dataKey={yKey}
              stroke="var(--cyan)"
              strokeWidth={2}
              dot={{ fill: 'var(--cyan)', r: 3 }}
            />
          </LineChart>
        )}
      </ResponsiveContainer>
    </div>
  );
};

export default ChartRenderer;
