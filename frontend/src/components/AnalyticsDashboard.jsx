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
        chart.data.labels        = data.analytics.map((d) => formatDate(d.date));
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