import { useMemo } from "react";
import {
  BarChart as ReBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import type { Dataset, BarChartMapping } from "../api/types";
import Skeleton from "./Skeleton";
import WarningPlaceholder from "./WarningPlaceholder";

const CHART_COLORS = [
  "var(--atlas-chart-1)",
  "var(--atlas-chart-2)",
  "var(--atlas-chart-3)",
  "var(--atlas-chart-4)",
];

interface Props {
  dataset: Dataset | null;
  mapping: BarChartMapping;
  options?: { title?: string };
}

export default function BarChart({ dataset, mapping, options }: Props) {
  const { x, y, aggregation, group_by, bar_mode } = mapping;

  // All hooks before any conditional returns
  const chartData = useMemo(() => {
    if (!dataset) return [];
    const { rows } = dataset;
    const groups = group_by
      ? [...new Set(rows.map(r => String(r[group_by] ?? "")))]
      : [];
    const categories = [...new Set(rows.map(r => String(r[x] ?? "")))];
    return categories.map(cat => {
      const catRows = rows.filter(r => String(r[x] ?? "") === cat);
      const entry: Record<string, unknown> = { [x]: cat };
      if (group_by) {
        for (const g of groups) {
          const gRows = catRows.filter(r => String(r[group_by] ?? "") === g);
          entry[g] = agg(gRows.map(r => Number(r[y] ?? 0)), aggregation);
        }
      } else {
        entry[y] = agg(catRows.map(r => Number(r[y] ?? 0)), aggregation);
      }
      return entry;
    });
  }, [dataset, x, y, aggregation, group_by]);

  // Early returns after hooks
  if (!dataset) return <Skeleton />;

  const { schema, rows } = dataset;
  const xCol = schema.find(c => c.key === x);
  const yCol = schema.find(c => c.key === y);
  if (!xCol)
    return <WarningPlaceholder reason={`key '${x}' not found in schema`} config={mapping} />;
  if (!yCol)
    return <WarningPlaceholder reason={`key '${y}' not found in schema`} config={mapping} />;
  if (yCol.type !== "number")
    return <WarningPlaceholder reason="y-axis field must be type: number" config={mapping} />;
  if (bar_mode && !group_by)
    return <WarningPlaceholder reason="`bar_mode` requires `group_by`" config={mapping} />;

  const groups = group_by
    ? [...new Set(rows.map(r => String(r[group_by] ?? "")))]
    : [];
  const stackId =
    bar_mode === "stacked" || bar_mode === "stacked_percent" ? "stack" : undefined;

  return (
    <div className="chart-container">
      {options?.title && (
        <h3 className="type-title chart-title">{options.title}</h3>
      )}
      <ResponsiveContainer width="100%" height={260}>
        <ReBarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--md-sys-color-outline-variant)" />
          <XAxis dataKey={x} tick={{ fontSize: 12 }} />
          <YAxis
            tick={{ fontSize: 12 }}
            tickFormatter={bar_mode === "stacked_percent" ? v => `${v}%` : undefined}
          />
          <Tooltip formatter={bar_mode === "stacked_percent" ? (v: number) => `${v.toFixed(1)}%` : undefined} />
          {groups.length > 0 && <Legend />}
          {group_by
            ? groups.map((g, i) => (
                <Bar key={g} dataKey={g} stackId={stackId} fill={CHART_COLORS[i % CHART_COLORS.length]} />
              ))
            : <Bar dataKey={y} fill={CHART_COLORS[0]} />}
        </ReBarChart>
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
