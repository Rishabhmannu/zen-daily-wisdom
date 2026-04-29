from __future__ import annotations

from zen_backend.services.telegram_client import (
    build_daily_html,
    escape_html_for_telegram,
)


def test_escape_html_for_telegram_handles_markup_chars() -> None:
    assert escape_html_for_telegram("<b>not bold</b>") == "&lt;b&gt;not bold&lt;/b&gt;"
    assert escape_html_for_telegram("a & b") == "a &amp; b"
    # Quotes are intentionally NOT escaped (Telegram's HTML parse_mode does
    # not require them) so prose stays readable.
    assert "\"" in escape_html_for_telegram("it's \"important\"")


def test_build_daily_html_has_expected_structure() -> None:
    body = build_daily_html(
        thought_of_day="Pause for one steady breath before the day pulls you in every direction.",
        theme_of_day="Patience",
        citation="Marcus Aurelius — Meditations IV.18",
        calendar_add_link="https://calendar.google.com/calendar/render?action=TEMPLATE&text=Theme",
    )
    assert "<b>Zen Daily Wisdom</b>" in body
    assert "<i>Theme: Patience</i>" in body
    assert "<i>Pause for one steady breath" in body
    assert "<b>Marcus Aurelius — Meditations IV.18</b>" in body
    assert "Add to Calendar" in body
    # No raw < or > leaked outside of the intentional tags we wrote.
    assert body.count("<b>") == 2
    assert body.count("<i>") == 2


def test_build_daily_html_escapes_user_content() -> None:
    body = build_daily_html(
        thought_of_day="A < B & C > D",
        theme_of_day="Math <ops>",
        citation="Some & body",
        calendar_add_link="https://example.com/?a=1&b=2",
    )
    assert "&lt; B &amp; C &gt;" in body
    assert "Math &lt;ops&gt;" in body
    assert "Some &amp; body" in body
    assert "?a=1&amp;b=2" in body
