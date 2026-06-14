from datetime import datetime, timezone
from app.extensions import db


class ShortenedUrl(db.Model):
    """
    Stores the mapping between a long URL and its 6-character short alias.
    """
    __tablename__ = "shortened_urls"

    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.Text, nullable=False)
    alias = db.Column(db.String(6), unique=True, nullable=False, index=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    clicks = db.relationship(
        "Click", back_populates="shortened_url", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<ShortenedUrl alias={self.alias!r} url={self.original_url[:40]!r}>"

    def to_dict(self):
        return {
            "id": self.id,
            "original_url": self.original_url,
            "alias": self.alias,
            "created_at": self.created_at.isoformat(),
            "total_clicks": len(self.clicks),
        }


class Click(db.Model):
    """
    Records every individual click/redirect event with a timestamp.
    Used for time-series analytics over the last 7 days.
    """
    __tablename__ = "clicks"

    id = db.Column(db.Integer, primary_key=True)
    shortened_url_id = db.Column(
        db.Integer,
        db.ForeignKey("shortened_urls.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clicked_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,   # indexed — queried heavily in range filters
    )
    ip_hash = db.Column(db.String(64), nullable=True)

    shortened_url = db.relationship("ShortenedUrl", back_populates="clicks")

    def __repr__(self):
        return f"<Click url_id={self.shortened_url_id} at={self.clicked_at}>"

    def to_dict(self):
        return {
            "id": self.id,
            "shortened_url_id": self.shortened_url_id,
            "clicked_at": self.clicked_at.isoformat(),
        }
