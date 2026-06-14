import { useState } from "react";
import UrlShortener from "./components/UrlShortener";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import styles from "./App.module.css";

export default function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleSuccess = () => {
    setRefreshTrigger((n) => n + 1);
  };

  return (
    <div className={styles.layout}>
      <main className={styles.main}>
        <UrlShortener onSuccess={handleSuccess} />
        <hr className={styles.divider} />
        <AnalyticsDashboard refreshTrigger={refreshTrigger} />
      </main>

      <footer className={styles.footer}>
        <p>
          Built with Flask + React &nbsp;·&nbsp; Rate limit: 5 URLs / min
        </p>
      </footer>
    </div>
  );
}