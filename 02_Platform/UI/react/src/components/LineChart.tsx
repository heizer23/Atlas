import { useMemo } from "react";
import {
  LineChart as ReLineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { Dataset, LineChartMapping } from "../api/types";
import Skeleton from "./Skeleton";
import WarningPlaceholder from "./WarningPlaceholder";

interface Props {
  dataset: Dataset | null;
  mapping: LineChartMapping;
  options?: { title?: string };
}

export default function LineChart({ dataset, mapping, options }: Props) {
  const { x, y, aggregation } = mapping;

  // Hook before any conditional returns
  const chartData = useMemo(() => {
    if (!dataset) return [];
    const { rows } = dataset;
    const xVals = [...new Set(rows.map(r => String(r[x] ?? "")))].sort();
    return xVals.map(xv => {
      const bucket = rows.filter(r => String(r[x] ?? "") === xv);
      return { [x]: xv, [y]: agg(bucket.map(r => Number(r[y] ?? 0)), aggregation) };
    });
  }, [dataset, x, y, aggregation]);

  if (!dataset) return <Skeleton />;

  const { schema } = dataset;
  const xCol = schema.find(c => c.key === x);
  const yCol = schema.find(c => c.key === y);
  if (!xCol)
    return <WarningPlaceholder reason={`key '${x}' not found in schema`} config={mapping} />;
  if (!yCol)
    return <WarningPlaceholder reason={`key '${y}' not found in schema`} config={mapping} />;
  if (yCol.type !== "number")
    return <WarningPlaceholder reason="y-axis field must be type: number" config={mapping} />;

  return (
    <div className="chart-container">
      {options?.title && (
        <h3 className="type-title chart-title">{options.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <ReLineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
          <XAxis dataKey={x} tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey={y}
            stroke="var(--atlas-chart-1)"
            strokeWidth={2}
            dot={{ r: 3, fill: "var(--atlas-chart-1)" }}
            activeDot={{ r: 5 }}
          />
        </ReLineChart>
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
