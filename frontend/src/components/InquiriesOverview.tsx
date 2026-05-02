import React, { useState } from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Sector } from 'recharts';

const data = [
  { name: 'Shopping', value: 45 },
  { name: 'Gas & Transport', value: 25 },
  { name: 'Grocery', value: 15 },
  { name: 'Entertainment', value: 10 },
  { name: 'Other', value: 5 },
];
const COLORS = ['var(--color-purple)', 'var(--color-blue)', 'var(--color-orange)', 'var(--color-yellow)', 'var(--text-secondary-dark)'];
const total = data.reduce((sum, entry) => sum + entry.value, 0);

const CustomTooltipContent = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="p-3 rounded-lg shadow-lg backdrop-blur-sm bg-slate-800/80 border-[var(--panel-border-dark)]">
        <p className="font-bold text-sm mb-1" style={{ color: payload[0].fill }}>{data.name}</p>
        <p className="text-xs">{`Frauds: ${data.value} (${(data.value / total * 100).toFixed(1)}%)`}</p>
      </div>
    );
  }
  return null;
};

const renderActiveShape = (props: any) => {
    const { cx, cy, innerRadius, outerRadius, startAngle, endAngle, fill } = props;
    return (
        <g>
            <Sector
                cx={cx}
                cy={cy}
                innerRadius={innerRadius}
                outerRadius={outerRadius + 6}
                startAngle={startAngle}
                endAngle={endAngle}
                fill={fill}
                style={{ filter: `drop-shadow(0 0 5px ${fill})` }}
            />
        </g>
    );
};

// FIX: The `activeIndex` prop is not recognized by TypeScript in some versions of recharts, causing a type error.
// Casting the Pie component to `any` allows passing the prop and preserves the intended hover functionality.
const PieWithActiveIndex = Pie as any;


const FraudCategoryChart: React.FC = () => {
    const [activeIndex, setActiveIndex] = useState<number | null>(null);

    const onPieEnter = (_: any, index: number) => {
        setActiveIndex(index);
    };

    const onPieLeave = () => {
        setActiveIndex(null);
    };

    const activeItem = activeIndex !== null ? data[activeIndex] : null;

    return (
        <div className="h-80 flex flex-col">
            <h3 className="text-lg font-semibold text-inherit mb-2 px-4">Top Fraud Categories</h3>
            <div className="flex-1 flex flex-col sm:flex-row items-center justify-center gap-4 sm:gap-8 px-4">
                <div className="relative w-48 h-48 flex-shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                            <Tooltip content={<CustomTooltipContent />} cursor={{fill: 'transparent'}} />
                            <PieWithActiveIndex
                                activeIndex={activeIndex}
                                activeShape={renderActiveShape}
                                data={data}
                                cx="50%"
                                cy="50%"
                                innerRadius={60}
                                outerRadius={80}
                                fill="#8884d8"
                                paddingAngle={2}
                                dataKey="value"
                                onMouseEnter={onPieEnter}
                                onMouseLeave={onPieLeave}
                            >
                                {data.map((_, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={COLORS[index % COLORS.length]}
                                        style={{
                                            opacity: activeIndex === null || activeIndex === index ? 1 : 0.5,
                                            transition: 'opacity 0.2s ease-in-out',
                                        }}
                                    />
                                ))}
                            </PieWithActiveIndex>
                        </PieChart>
                    </ResponsiveContainer>
                     <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none transition-opacity duration-300">
                        {activeItem ? (
                             <>
                                <span className="text-3xl font-bold" style={{ color: COLORS[activeIndex!] }}>
                                    {`${(activeItem.value / total * 100).toFixed(0)}%`}
                                </span>
                                <span className="text-sm text-[var(--text-secondary-dark)] font-semibold truncate max-w-[80px] text-center">{activeItem.name}</span>
                             </>
                        ) : (
                             <>
                                <span className="text-4xl font-bold">{total}</span>
                                <span className="text-sm text-[var(--text-secondary-dark)]">Total Frauds</span>
                             </>
                        )}
                    </div>
                </div>
                
                <div className="w-full sm:w-48">
                    <ul className="space-y-1">
                        {data.map((item, index) => (
                            <li 
                                key={item.name}
                                onMouseEnter={() => setActiveIndex(index)}
                                onMouseLeave={() => setActiveIndex(null)}
                                className="flex items-center justify-between p-2 rounded-md transition-all duration-300 cursor-pointer"
                                style={{ 
                                    opacity: activeIndex === null || activeIndex === index ? 1 : 0.6,
                                    backgroundColor: activeIndex === index ? 'rgba(255,255,255,0.05)' : 'transparent'
                                }}
                            >
                                <div className="flex items-center gap-3">
                                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: COLORS[index % COLORS.length] }}></div>
                                    <span className="text-sm font-medium truncate">{item.name}</span>
                                </div>
                                <span className="text-sm font-bold text-gray-300 ml-2">{item.value}</span>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    );
};

export default FraudCategoryChart;