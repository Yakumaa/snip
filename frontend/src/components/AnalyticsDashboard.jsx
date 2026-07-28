import { useState, useEffect, useRef, useCallback } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "react-chartjs-2";
import { fetchAllUrls, fetchAnalytics } from "../services/api";
import QrCodeBlock from "./QrCodeBlock";
import styles from "./AnalyticsDashboard.module.css";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Sub-components
function UrlListItem({ entry, isSelected, onClick }) {
  return (
    <button
      type="button"
      className={`${styles.urlItem} ${isSelected ? styles.urlItemActive : ""}`}
      onClick={() => onClick(entry)}
      aria-pressed={isSelected}
    >
      <span className={styles.urlAlias}>/{entry.alias}</span>
      <span className={styles.urlMeta}>
        {/* <span className={styles.urlClicks}>
          <ClickIcon />
          {entry.total_clicks.toLocaleString()}
        </span> */}
        <span className={styles.urlOrigin} title={entry.original_url}>
          {truncateUrl(entry.original_url, 32)}
        </span>
      </span>
    </button>
  );
}

function EmptyState() {
  return (
    <div className={styles.emptyState}>
      <ChartBarIcon />
      <p>No URLs shortened yet.</p>
      <p className={styles.emptyHint}>Create one above and it'll appear here.</p>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className={styles.chartSkeleton} aria-busy="true" aria-label="Loading chart…">
      {[40, 65, 45, 80, 55, 90, 70].map((h, i) => (
        <div key={i} className={styles.skeletonBar} style={{ height: `${h}%` }} />
      ))}
    </div>
  );
}

// Enhanced analytics breakdowns (devices / browsers / OS / countries / referrers)
const DEVICE_LABELS = {
  desktop: "Desktop",
  mobile: "Mobile",
  tablet: "Tablet",
  bot: "Bot",
  other: "Other",
  unknown: "Unknown",
};

function deviceIcon(deviceType) {
  switch (deviceType) {
    case "mobile":
      return <PhoneIcon />;
    case "tablet":
      return <TabletIcon />;
    case "bot":
      return <BotIcon />;
    case "desktop":
      return <MonitorIcon />;
    default:
      return <HelpIcon />;
  }
}

function countryFlagEmoji(countryCode) {
  if (!countryCode || countryCode.length !== 2) return "🌐";
  const codePoints = [...countryCode.toUpperCase()].map(
    (char) => 127397 + char.charCodeAt(0)
  );
  return String.fromCodePoint(...codePoints);
}

/**
 * One row of a breakdown card: a label, a proportional bar, and a count.
 * `total` is the sum across all rows in *this* breakdown (not the URL's
 * overall total_clicks) so a bar always reads as "share of this chart".
 */
function BreakdownRow({ icon, label, count, total }) {
  const pct = total > 0 ? Math.round((count / total) * 100) : 0;
  return (
    <div className={styles.breakdownRow}>
      <div className={styles.breakdownRowLabel}>
        {icon && <span className={styles.breakdownRowIcon}>{icon}</span>}
        <span className={styles.breakdownRowText} title={label}>
          {label}
        </span>
      </div>
      <div className={styles.breakdownRowBarTrack} aria-hidden="true">
        <div className={styles.breakdownRowBarFill} style={{ width: `${pct}%` }} />
      </div>
      <span className={styles.breakdownRowCount}>{count.toLocaleString()}</span>
    </div>
  );
}

function BreakdownCard({ title, icon, rows, emptyLabel = "No data yet" }) {
  const total = rows.reduce((sum, r) => sum + r.count, 0);
  return (
    <div className={styles.breakdownCard}>
      <div className={styles.breakdownCardHeader}>
        <span className={styles.breakdownCardIcon}>{icon}</span>
        <h3 className={styles.breakdownCardTitle}>{title}</h3>
      </div>

      {rows.length === 0 ? (
        <p className={styles.breakdownEmpty}>{emptyLabel}</p>
      ) : (
        <div className={styles.breakdownRows}>
          {rows.map((r) => (
            <BreakdownRow
              key={r.label}
              icon={r.icon}
              label={r.label}
              count={r.count}
              total={total}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// Main component
export default function AnalyticsDashboard({ refreshTrigger }) {
  const [urls, setUrls] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(null);

  const [selected, setSelected] = useState(null);   // full URL object
  const [analytics, setAnalytics] = useState(null);   // API response
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const chartRef = useRef(null);

  useEffect(() => {
    let cancelled = false;

    async function loadUrls() {
      setListLoading(true);
      setListError(null);
      try {
        const data = await fetchAllUrls();
        if (!cancelled) setUrls(data);
      } catch (err) {
        if (!cancelled) setListError(err.message ?? "Failed to load URLs.");
      } finally {
        if (!cancelled) setListLoading(false);
      }
    }

    loadUrls();
    return () => { cancelled = true; };
  }, [refreshTrigger]);  

  const loadAnalytics = useCallback(async (alias) => {
    setChartLoading(true);
    setChartError(null);
    try {
      const data = await fetchAnalytics(alias);
      setAnalytics(data);
      setLastRefreshed(new Date());

      setUrls((prev) =>
        prev.map((u) =>
          u.alias === alias ? { ...u, total_clicks: data.total_clicks } : u
        )
      );

      if (chartRef.current) {
        const chart = chartRef.current;
        chart.data.labels = data.analytics.map((d) => formatDate(d.date));
        chart.data.datasets[0].data = data.analytics.map((d) => d.clicks);
        chart.update("active"); 
      }
    } catch (err) {
      setChartError(err.message ?? "Failed to load analytics.");
    } finally {
      setChartLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selected) loadAnalytics(selected.alias);
  }, [selected, loadAnalytics]);

  // Handlers
  const handleSelectUrl = (entry) => {
    if (selected?.alias === entry.alias) return;
    setAnalytics(null);   
    setSelected(entry);
  };

  const handleRefresh = () => {
    if (selected && !chartLoading) loadAnalytics(selected.alias);
  };

  // Chart.js config
  const chartData = analytics
    ? {
        labels: analytics.analytics.map((d) => formatDate(d.date)),
        datasets: [
          {
            label: "Clicks",
            data: analytics.analytics.map((d) => d.clicks),
            fill: true,
            tension: 0.4,
            borderColor: "rgba(99, 102, 241, 1)",        
            backgroundColor: "rgba(99, 102, 241, 0.12)",
            pointBackgroundColor: "rgba(99, 102, 241, 1)",
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7,
          },
        ],
      }
    : null;

  // Enhanced analytics rows — reshaped from the API response into the
  // {label, count, icon?} shape BreakdownCard expects. Kept as plain
  // derived values (no useMemo) since these are small arrays (≤15 rows)
  // recomputed only when `analytics` itself changes.
  const deviceRows = analytics
    ? analytics.devices.map((d) => ({
        label: DEVICE_LABELS[d.device_type] ?? d.device_type,
        count: d.clicks,
        icon: deviceIcon(d.device_type),
      }))
    : [];

  const browserRows = analytics
    ? analytics.browsers.map((b) => ({ label: b.browser, count: b.clicks }))
    : [];

  const osRows = analytics
    ? analytics.operating_systems.map((o) => ({ label: o.os, count: o.clicks }))
    : [];

  const countryRows = analytics
    ? analytics.countries.map((c) => ({
        label: c.country,
        count: c.clicks,
        icon: <span className={styles.flagEmoji}>{countryFlagEmoji(c.country_code)}</span>,
      }))
    : [];

  const referrerRows = analytics
    ? analytics.top_referrers.map((r) => ({ label: r.referrer, count: r.clicks }))
    : [];

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 500 },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) =>
            ` ${ctx.parsed.y} click${ctx.parsed.y !== 1 ? "s" : ""}`,
        },
      },
    },
    scales: {
      x: {
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: { color: "#94a3b8", font: { size: 12 } },
      },
      y: {
        beginAtZero: true,
        grid: { color: "rgba(255,255,255,0.06)" },
        ticks: {
          color: "#94a3b8",
          font: { size: 12 },
          stepSize: 1,
          precision: 0,
        },
      },
    },
  };

  // Render
  return (
    <section className={styles.dashboard}>
      <header className={styles.dashHeader}>
        <h2 className={styles.dashTitle}>Analytics</h2>
        <p className={styles.dashSubtitle}>
          Select a link to see its 7-day click history.
        </p>
      </header>

      <div className={styles.dashBody}>
        <aside className={styles.urlList} aria-label="Shortened URL list">
          {listLoading && (
            <div className={styles.listLoading} aria-busy="true">
              {[...Array(4)].map((_, i) => (
                <div key={i} className={styles.listSkeleton} />
              ))}
            </div>
          )}

          {listError && (
            <p className={styles.listError} role="alert">
              {listError}
            </p>
          )}

          {!listLoading && !listError && urls.length === 0 && <EmptyState />}

          {!listLoading &&
            urls.map((entry) => (
              <UrlListItem
                key={entry.alias}
                entry={entry}
                isSelected={selected?.alias === entry.alias}
                onClick={handleSelectUrl}
              />
            ))}
        </aside>

        <div className={styles.chartPanel}>
          {!selected && (
            <div className={styles.chartPlaceholder}>
              <ChartLineIcon />
              <p>Pick a link on the left to load its chart.</p>
            </div>
          )}

          {selected && (
            <>
              <div className={styles.chartHeader}>
                <div className={styles.chartMeta}>
                  <span className={styles.chartAlias}>/{selected.alias}</span>
                  <a
                    href={selected.original_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={styles.chartOriginalUrl}
                    title={selected.original_url}
                  >
                    {truncateUrl(selected.original_url, 50)}
                  </a>
                </div>

                <button
                  type="button"
                  className={`${styles.refreshBtn} ${chartLoading ? styles.refreshBtnSpinning : ""}`}
                  onClick={handleRefresh}
                  disabled={chartLoading}
                  aria-label="Refresh chart data"
                  title={lastRefreshed ? `Last refreshed ${formatTime(lastRefreshed)}` : "Refresh"}
                >
                  <RefreshIcon />
                  {chartLoading ? "Refreshing…" : "Refresh"}
                </button>
              </div>

              <div className={styles.statsAndQr}>
                {analytics && (
                  <div className={styles.statsRow}>
                    <Stat
                      label="Total clicks"
                      value={analytics.total_clicks.toLocaleString()}
                    />
                    <Stat
                      label="Last 7 days"
                      value={analytics.analytics
                        .reduce((s, d) => s + d.clicks, 0)
                        .toLocaleString()}
                    />
                    <Stat
                      label="Peak day"
                      value={Math.max(...analytics.analytics.map((d) => d.clicks)).toLocaleString()}
                    />
                  </div>
                )}

                <div className={styles.analyticsQr}>
                  <QrCodeBlock qrCodeUrl={selected.qr_code_url} alias={selected.alias} size={64} compact />
                </div>
              </div>

              {chartError && (
                <p className={styles.chartError} role="alert">
                  {chartError}
                </p>
              )}

              <div className={styles.chartWrap}>
                {chartLoading && !analytics && <ChartSkeleton />}
                {chartData && (
                  <Line
                    key={selected.alias}
                    ref={chartRef}
                    data={chartData}
                    options={chartOptions}
                  />
                )}
              </div>

              {lastRefreshed && (
                <p className={styles.lastRefreshed}>
                  Updated {formatTime(lastRefreshed)}
                </p>
              )}
            </>
          )}
        </div>
      </div>

      {selected && analytics && (
        <div className={styles.breakdownsGrid}>
          <BreakdownCard title="Devices" icon={<MonitorIcon />} rows={deviceRows} />
          <BreakdownCard title="Browsers" icon={<CompassIcon />} rows={browserRows} />
          <BreakdownCard title="Operating Systems" icon={<LayersIcon />} rows={osRows} />
          <BreakdownCard
            title="Top Countries"
            icon={<GlobeIcon />}
            rows={countryRows}
            emptyLabel="No location data yet — geolocation only resolves for public IPs."
          />
          <BreakdownCard
            title="Top Referrers"
            icon={<LinkIcon />}
            rows={referrerRows}
            emptyLabel="No referrer data yet."
          />
        </div>
      )}
    </section>
  );
}

// Tiny stat tile
function Stat({ label, value }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}

// Utilities
function truncateUrl(url, max) {
  try {
    const { hostname, pathname } = new URL(url);
    const short = hostname + pathname;
    return short.length > max ? short.slice(0, max) + "…" : short;
  } catch {
    return url.length > max ? url.slice(0, max) + "…" : url;
  }
}

function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function formatTime(date) {
  return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
}

// Inline SVG icons
// function ClickIcon() {
//   return (
//     <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
//       <path d="M3 3l7.07 16.97 2.51-7.39 7.39-2.51L3 3z" />
//     </svg>
//   );
// }

function ChartBarIcon() {
  return (
    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <line x1="18" y1="20" x2="18" y2="10" />
      <line x1="12" y1="20" x2="12" y2="4" />
      <line x1="6" y1="20" x2="6" y2="14" />
      <line x1="2" y1="20" x2="22" y2="20" />
    </svg>
  );
}

function ChartLineIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  );
}

function RefreshIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function MonitorIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <line x1="8" y1="21" x2="16" y2="21" />
      <line x1="12" y1="17" x2="12" y2="21" />
    </svg>
  );
}

function PhoneIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="7" y="2" width="10" height="20" rx="2" />
      <line x1="11" y1="18" x2="13" y2="18" />
    </svg>
  );
}

function TabletIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="2" width="16" height="20" rx="2" />
      <line x1="12" y1="18" x2="12.01" y2="18" />
    </svg>
  );
}

function BotIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="4" y="8" width="16" height="12" rx="2" />
      <circle cx="9" cy="14" r="1" />
      <circle cx="15" cy="14" r="1" />
      <line x1="12" y1="4" x2="12" y2="8" />
      <circle cx="12" cy="3" r="1" />
    </svg>
  );
}

function HelpIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function CompassIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  );
}

function LayersIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
    </svg>
  );
}