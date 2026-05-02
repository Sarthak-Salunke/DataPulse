import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const data = [
  { name: '$0-50', Normal: 1200, Fraud: 5 },
  { name: '$50-100', Normal: 800, Fraud: 12 },
  { name: '$100-500', Normal: 400, Fraud: 45 },
  { name: '$500-1k', Normal: 150, Fraud: 28 },
  { name: '$1k+', Normal: 50, Fraud: 18 },
];

const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        return (
            <div className="p-3 rounded-lg shadow-lg backdrop-blur-sm bg-slate-800/80 border-[var(--panel-border-dark)]">
                 <p className="font-bold text-sm mb-1">{`Amount: ${label}`}</p>
                {payload.map((p: any) => (
                    <p key={p.name} style={{ color: p.fill.startsWith('url') ? (p.name === 'Fraud' ? 'var(--color-red)' : 'var(--color-green)') : p.fill }} className="text-xs">{`${p.name}: ${p.value}`}</p>
                ))}
            </div>
        );
    }
    return null;
};

const AmountDistributionChart = () => {
    const axisColor = 'var(--text-secondary-dark)';
    const gridColor = 'var(--border-color-dark)';

    return (
        <div className="h-64">
             <h3 className="text-lg font-bold text-inherit mb-4">Fraud Distribution by Amount</h3>
            <ResponsiveContainer width="100%" height="100%">
                 <BarChart data={data} margin={{ top: 5, right: 20, left: -25, bottom: 20 }}>
                     <defs>
                        <linearGradient id="barNormal" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="rgba(34, 197, 94, 0.7)" />
                            <stop offset="100%" stopColor="rgba(34, 197, 94, 0.3)" />
                        </linearGradient>
                        <linearGradient id="barFraud" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="rgba(239, 68, 68, 0.8)" />
                            <stop offset="100%" stopColor="rgba(239, 68, 68, 0.4)" />
                        </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
                    <XAxis dataKey="name" stroke={axisColor} tick={{ fontSize: 12 }} />
                    <YAxis stroke={axisColor} tick={{ fontSize: 12 }} />
                    <Tooltip content={<CustomTooltip />} cursor={{fill: 'rgba(124, 58, 237, 0.1)'}}/>
                    <Legend wrapperStyle={{fontSize: "12px"}}/>
                    <Bar dataKey="Normal" stackId="a" fill="url(#barNormal)" />
                    <Bar dataKey="Fraud" stackId="a" fill="url(#barFraud)" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
    );
};

export default AmountDistributionChart;