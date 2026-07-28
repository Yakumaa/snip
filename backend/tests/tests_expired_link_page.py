import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.routes import urls as urls_module


class FakeQuery:
    def __init__(self, entry):
        self._entry = entry

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._entry


def test_expired_link_renders_custom_error_page(monkeypatch):
    expired_entry = type(
        "ExpiredEntry",
        (),
        {"expires_at": datetime.now(timezone.utc) - timedelta(days=1)},
    )()

    class FakeShortenedUrl:
        query = FakeQuery(expired_entry)

    monkeypatch.setattr(urls_module, "ShortenedUrl", FakeShortenedUrl)

    app = create_app()
    app.testing = True
    client = app.test_client()

    response = client.get("/expired-alias")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/?expired=1&alias=expired-alias")
    print("PASS  test_expired_link_renders_custom_error_page")


if __name__ == "__main__":
    from _pytest.monkeypatch import MonkeyPatch

    monkeypatch = MonkeyPatch()
    try:
        test_expired_link_renders_custom_error_page(monkeypatch)
    except Exception as exc:
        print(f"FAIL  test_expired_link_renders_custom_error_page ({exc})")
        raise
    finally:
        monkeypatch.undo()
