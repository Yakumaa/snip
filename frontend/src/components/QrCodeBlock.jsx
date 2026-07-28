import styles from "./QrCodeBlock.module.css";

/**
 * Small QR-code preview + download affordance.
 *
 * `qrCodeUrl` is the absolute PNG endpoint the backend already returns (e.g. from /api/shorten or /api/urls) — no fetching or base64 decoding needed here, it's used directly as an <img src>.
 *
 * The download link appends `&download=1`, which asks the backend to set `Content-Disposition: attachment` — the HTML `download` attribute alone isn't reliably honoured by browsers for cross-origin resources (frontend and backend can be on different ports/domains), so the server-side header is what actually guarantees "Save As" behaviour.
 */
export default function QrCodeBlock({ qrCodeUrl, alias, size = 88, compact = false }) {
  if (!qrCodeUrl) return null;

  const downloadUrl = `${qrCodeUrl}${qrCodeUrl.includes("?") ? "&" : "?"}download=1`;

  return (
    <div className={`${styles.qrSection} ${compact ? styles.qrSectionCompact : ""}`}>
      <div className={styles.qrImageWrap} style={{ width: size , height: size }}>
        <img
          src={qrCodeUrl}
          alt={`QR code linking to /${alias}`}
          width={size}
          height={size}
          className={styles.qrImage}
          loading="lazy"
        />
      </div>

      <div className={styles.qrMeta}>
        <span className={styles.qrLabel}>Scan to open</span>
        <a href={downloadUrl} download={`snip-${alias}-qr.png`} className={styles.qrDownloadBtn}>
          <DownloadIcon aria-hidden="true" /> Download PNG
        </a>
      </div>
    </div>
  );
}

function DownloadIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}
