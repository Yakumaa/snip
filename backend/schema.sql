-- shortened_urls 
CREATE TABLE IF NOT EXISTS shortened_urls (
    id           SERIAL PRIMARY KEY,
    original_url TEXT        NOT NULL,
    alias        VARCHAR(6)  NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_shortened_urls_alias UNIQUE (alias)
);

-- Fast alias look-ups on every redirect request
CREATE INDEX IF NOT EXISTS idx_shortened_urls_alias
    ON shortened_urls (alias);

-- clicks
CREATE TABLE IF NOT EXISTS clicks (
    id                SERIAL PRIMARY KEY,
    shortened_url_id  INTEGER      NOT NULL,
    clicked_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    ip_hash           VARCHAR(64),
    referrer          TEXT,
    user_agent        TEXT,
    browser           VARCHAR(50),
    os                VARCHAR(50),
    device_type       VARCHAR(20),
    country           VARCHAR(100),
    country_code      VARCHAR(2),
    city              VARCHAR(100),

    CONSTRAINT fk_clicks_shortened_url
        FOREIGN KEY (shortened_url_id)
        REFERENCES shortened_urls (id)
        ON DELETE CASCADE
);

-- Composite index: filter by URL + time range in one scan
CREATE INDEX IF NOT EXISTS idx_clicks_url_id_clicked_at
    ON clicks (shortened_url_id, clicked_at DESC);

-- Analytics indexes for GROUP BY queries (matching migration 0ede9771497f)
CREATE INDEX IF NOT EXISTS ix_clicks_browser
    ON clicks (browser);
CREATE INDEX IF NOT EXISTS ix_clicks_country_code
    ON clicks (country_code);
CREATE INDEX IF NOT EXISTS ix_clicks_device_type
    ON clicks (device_type);
CREATE INDEX IF NOT EXISTS ix_clicks_os
    ON clicks (os);

-- analytics view (convenience) 
CREATE OR REPLACE VIEW v_clicks_last_7_days AS
SELECT
    su.alias,
    DATE(c.clicked_at AT TIME ZONE 'UTC') AS click_date,
    COUNT(*)                               AS click_count
FROM clicks c
JOIN shortened_urls su ON su.id = c.shortened_url_id
WHERE c.clicked_at >= NOW() - INTERVAL '7 days'
GROUP BY su.alias, click_date
ORDER BY su.alias, click_date;

ALTER TABLE shortened_urls ADD COLUMN expires_at TIMESTAMPTZ;
