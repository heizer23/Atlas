import { useMemo } from "react";
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { Dataset, ComboChartMapping } from "../api/types";
import Skeleton from "./Skeleton";
import WarningPlaceholder from "./WarningPlaceholder";

const BAR_COLORS  = ["var(--atlas-chart-1)", "var(--atlas-chart-2)"];
const LINE_COLORS = ["var(--atlas-chart-line-1)", "var(--atlas-chart-line-2)"];

interface Props {
  dataset: Dataset | null;
  mapping: ComboChartMapping;
  options?: { title?: string };
}

export default function ComboChart({ dataset, mapping, options }: Props) {
  const { x, series } = mapping;

  // Hook before any conditional returns
  const chartData = useMemo(() => {
    if (!dataset) return [];
    const { rows } = dataset;
    const xVals = [...new Set(rows.map(r => String(r[x] ?? "")))].sort();
    return xVals.map(xv => {
      const bucket = rows.filter(r => String(r[x] ?? "") === xv);
      const entry: Record<string, unknown> = { [x]: xv };
      for (const s of series) {
        entry[s.y] = agg(bucket.map(r => Number(r[s.y] ?? 0)), s.aggregation);
      }
      return entry;
    });
  }, [dataset, x, series]);

  if (!dataset) return <Skeleton />;

  const { schema } = dataset;

  if (series.length < 2)
    return <WarningPlaceholder reason="ComboChart requires ≥2 series" suggestion="Use BarChart or LineChart for a single series" config={mapping} />;
  if (!series.some(s => s.type === "bar"))
    return <WarningPlaceholder reason="ComboChart requires ≥1 bar series" config={mapping} />;
  if (!series.some(s => s.type === "line"))
    return <WarningPlaceholder reason="ComboChart requires ≥1 line series" config={mapping} />;

  const rightSeries = series.filter(s => s.y_axis === "right");
  const leftSeries  = series.filter(s => s.y_axis !== "right");
  if (rightSeries.length > 0 && leftSeries.length === 0)
    return <WarningPlaceholder reason="dual axis requires ≥1 series on left" config={mapping} />;

  if (!schema.find(c => c.key === x))
    return <WarningPlaceholder reason={`key '${x}' not found in schema`} config={mapping} />;

  for (const s of series) {
    const col = schema.find(c => c.key === s.y);
    if (!col) return <WarningPlaceholder reason={`key '${s.y}' not found in schema`} config={mapping} />;
    if (col.type !== "number") return <WarningPlaceholder reason={`y-axis field '${s.y}' must be type: number`} config={mapping} />;
  }

  const hasDualAxis = rightSeries.length > 0;
  let barIdx = 0, lineIdx = 0;

  return (
    <div className="chart-container">
      {options?.title && (
        <h3 className="type-title chart-title">{options.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
          <XAxis dataKey={x} tick={{ fontSize: 12 }} />
          <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
          {hasDualAxis && <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />}
          <Tooltip />
          <Legend />
          {series.map(s => {
            const axisId = s.y_axis === "right" ? "right" : "left";
            const label  = s.label ?? s.y;
            if (s.type === "bar") {
              const color = BAR_COLORS[barIdx++ % BAR_COLORS.length];
              return <Bar key={s.y} dataKey={s.y} name={label} fill={color} yAxisId={axisId} />;
            } else {
              const color = LINE_COLORS[lineIdx++ % LINE_COLORS.length];
              return <Line key={s.y} type="monotone" dataKey={s.y} name={label} stroke={color} strokeWidth={2} dot={{ r: 3, fill: color }} yAxisId={axisId} />;
            }
          })}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

function agg(vals: number[], method: string): number {
  if (!vals.length) return 0;
  switch (method) {
    case "sum":   return vals.reduce((a, b) => a + b, 0);
    case "avg":   return vals.reduce((a, b) => a + b, 0) / vals.length;
    case "count": return vals.length;
    case "max":   return Math.max(...vals);
    case "min":   return Math.min(...vals);
    default:      return 0;
  }
}
