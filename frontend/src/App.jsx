import { useMemo, useState } from "react";
import { useLocation } from "react-router-dom";
import UrlShortener from "./components/UrlShortener";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import ExpiredLinkPage from "./components/ExpiredLinkPage";
import styles from "./App.module.css";

export default function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [activeTab, setActiveTab] = useState("shorten");
  const location = useLocation();

  const isExpiredRoute = useMemo(() => {
    const params = new URLSearchParams(location.search);
    return params.get("expired") === "1";
  }, [location.search]);

  const handleSuccess = () => {
    setRefreshTrigger((n) => n + 1);
  };

  if (isExpiredRoute) {
    return <ExpiredLinkPage />;
  }

  return (
    <div className={styles.root}>

      <header className={styles.navbar}>
        <div className={styles.navInner}>
          <span className={styles.navLogo}>
            snip<span className={styles.navDot}>.</span>
          </span>

          <nav className={styles.navTabs} aria-label="Main navigation">
            <button
              type="button"
              className={`${styles.navTab} ${activeTab === "shorten" ? styles.navTabActive : ""}`}
              onClick={() => setActiveTab("shorten")}
              aria-current={activeTab === "shorten" ? "page" : undefined}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
                <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
              </svg>
              Shorten
            </button>

            <button
              type="button"
              className={`${styles.navTab} ${activeTab === "analytics" ? styles.navTabActive : ""}`}
              onClick={() => setActiveTab("analytics")}
              aria-current={activeTab === "analytics" ? "page" : undefined}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/><line x1="2" y1="20" x2="22" y2="20"/>
              </svg>
              Analytics
            </button>
          </nav>

          <span className={styles.navBadge} aria-label="Rate limit info">
            5 / min
          </span>
        </div>
      </header>

      <main className={styles.main}>

        <section
          className={`${styles.panel} ${activeTab === "shorten" ? styles.panelVisible : styles.panelHidden}`}
          aria-hidden={activeTab !== "shorten"}
        >
          <div className={styles.heroWrap}>
            <UrlShortener onSuccess={handleSuccess} />
          </div>
        </section>

        <section
          className={`${styles.panel} ${activeTab === "analytics" ? styles.panelVisible : styles.panelHidden}`}
          aria-hidden={activeTab !== "analytics"}
        >
          <div className={styles.analyticsWrap}>
            <AnalyticsDashboard refreshTrigger={refreshTrigger} />
          </div>
        </section>

      </main>

      <footer className={styles.footer}>
        <p>Built with Flask + React · PostgreSQL · Docker</p>
      </footer>
    </div>
  );
}