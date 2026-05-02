import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, ReferenceLine } from 'recharts';

const data = Array.from({ length: 12 }, (_, i) => ({
  name: `${i * 2}:00`,
  Normal: Math.floor(Math.random() * 200 + 800),
  Fraud: Math.floor(Math.random() * 20 + 10) + (i > 4 && i < 9 ? i * 5 : 0),
}));

const CustomTooltip = ({ active, payload, label }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="p-3 rounded-lg shadow-lg backdrop-blur-sm bg-slate-800/80 border-[var(--panel-border-dark)]">
        <p className="font-bold text-sm mb-1">{`Time: ${label}`}</p>
        {payload.map((p: any) => (
          <p key={p.name} style={{ color: p.stroke }} className="text-xs">{`${p.name}: ${p.value}`}</p>
        ))}
      </div>
    );
  }
  return null;
};

const FraudOverTimeChart = () => {
  const axisColor = 'var(--text-secondary-dark)';
  const gridColor = 'var(--border-color-dark)';

  return (
    <div className="h-64">
      <h3 className="text-lg font-bold text-inherit mb-4">Transactions Over Time</h3>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 5, right: 20, left: -15, bottom: 20 }}>
          <defs>
            <linearGradient id="colorNormal" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-green)" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="var(--color-green)" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="colorFraud" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="var(--color-red)" stopOpacity={0.4}/>
              <stop offset="95%" stopColor="var(--color-red)" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={gridColor} />
          <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{fill: axisColor, fontSize: 12}} dy={10} />
          <YAxis axisLine={false} tickLine={false} tick={{fill: axisColor, fontSize: 12}} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{fontSize: "12px", paddingTop: "20px"}}/>
          <ReferenceLine y={45} label={{ value: 'Alert Threshold', position: 'insideTopLeft', fill: 'var(--color-yellow)', fontSize: 10, dy: 10 }} stroke="var(--color-yellow)" strokeDasharray="3 3" ifOverflow="extendDomain" />
          <Area type="monotone" dataKey="Normal" stroke="var(--color-green)" strokeWidth={2} fill="url(#colorNormal)" dot={false} activeDot={{ r: 6 }} />
          <Area type="monotone" dataKey="Fraud" stroke="var(--color-red)" strokeWidth={2} fill="url(#colorFraud)" dot={false} activeDot={{ r: 6 }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

export default FraudOverTimeChart;