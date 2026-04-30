"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type DailySeriesPoint = {
  date: string; // ISO YYYY-MM-DD
  mood: number | null;
  submissions: number;
  windows: string[];
};

type Props = {
  series: DailySeriesPoint[];
};

const SHORT_DATE = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
});

const LONG_DATE = new Intl.DateTimeFormat(undefined, {
  weekday: "long",
  month: "long",
  day: "numeric",
});

function formatShortDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return SHORT_DATE.format(d);
}

function formatLongDate(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return LONG_DATE.format(d);
}

type TooltipPayloadEntry = {
  payload: DailySeriesPoint;
  value: number | null;
};

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload || payload.length === 0) return null;
  const point = payload[0].payload;
  const moodLabel =
    point.mood === null ? "no submissions" : `${Math.round(point.mood)} / 100`;
  return (
    <div className="zen-chart-tooltip">
      <div className="zen-chart-tooltip-date">{formatLongDate(label ?? point.date)}</div>
      <div className="zen-chart-tooltip-mood">{moodLabel}</div>
      {point.windows.length > 0 ? (
        <div className="zen-chart-tooltip-meta">{point.windows.join(", ")}</div>
      ) : null}
    </div>
  );
}

export function MoodLineChart({ series }: Props) {
  const hasAnyData = series.some((p) => p.mood !== null);
  if (!hasAnyData) {
    return (
      <div className="zen-chart-empty">
        <p className="zen-note" style={{ margin: 0 }}>
          Submit your first check-in and your mood trend will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="zen-chart-wrapper" aria-label="Mood over the last 14 days">
      <ResponsiveContainer width="100%" height={220}>
        <LineChart
          data={series}
          margin={{ top: 8, right: 12, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id="zenMoodLine" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#6c9b7a" />
              <stop offset="100%" stopColor="#2f5b4f" />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#e3d4c1" strokeDasharray="3 5" vertical={false} />
          <XAxis
            dataKey="date"
            stroke="#7a6e62"
            tick={{ fill: "#5e564e", fontSize: 11 }}
            tickLine={false}
            tickFormatter={formatShortDate}
            interval="preserveStartEnd"
            minTickGap={24}
          />
          <YAxis
            domain={[0, 100]}
            ticks={[0, 25, 50, 75, 100]}
            stroke="#7a6e62"
            tick={{ fill: "#5e564e", fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={32}
          />
          <ReferenceLine
            y={50}
            stroke="#cdbda8"
            strokeDasharray="4 4"
            ifOverflow="extendDomain"
          />
          <Tooltip
            content={<ChartTooltip />}
            cursor={{ stroke: "#cdbda8", strokeWidth: 1, strokeDasharray: "4 4" }}
          />
          <Line
            type="monotone"
            dataKey="mood"
            stroke="url(#zenMoodLine)"
            strokeWidth={2.5}
            dot={{ r: 3.5, fill: "#2f5b4f", stroke: "#fdf8f1", strokeWidth: 1.5 }}
            activeDot={{ r: 5, fill: "#2f5b4f", stroke: "#fff", strokeWidth: 2 }}
            connectNulls={false}
            isAnimationActive
            animationDuration={700}
            animationEasing="ease-out"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
