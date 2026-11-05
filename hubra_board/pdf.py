"""The GV invitation and minutes as PDF (WeasyPrint, no outside files)."""

from __future__ import annotations

from datetime import datetime, timezone

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

_STYLE = """
@page { size: A4; margin: 22mm 20mm 20mm 22mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #777; } }
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 10pt; color: #222; line-height: 1.45; }
.club { font-size: 9pt; color: #666; text-transform: uppercase; letter-spacing: .08em; }
h1 { font-size: 17pt; margin: 4mm 0 2mm; }
h2 { font-size: 11pt; margin: 6mm 0 1.5mm; }
.meta { margin: 0 0 6mm; }
.meta td { padding: 0 6mm 1mm 0; vertical-align: top; }
.meta td:first-child { color: #666; }
ol.agenda { padding-left: 6mm; }
ol.agenda li { margin-bottom: 2mm; }
.desc, .min { white-space: pre-wrap; }
.desc { color: #555; }
.decision { margin-top: 1.5mm; padding: 1.5mm 3mm; border-left: 2pt solid #6d4bd8; background: #f5f2fd; }
.vote { margin-top: 1.5mm; font-size: 9pt; }
.vote td { padding: 0 4mm 0 0; }
.sign { margin-top: 16mm; width: 100%; }
.sign td { width: 50%; padding-top: 12mm; border-top: .6pt solid #999; font-size: 9pt; color: #555; }
.sign td + td { padding-left: 8mm; }
.small { font-size: 8.5pt; color: #666; }
"""

_INVITATION = _env.from_string(
    """<!doctype html><html lang="{{ lang }}"><head><meta charset="utf-8">
<style>{{ style }}</style></head><body>
<div class="club">{{ club }}</div>
<h1>{{ t.invitation }}: {{ m.title }}</h1>
<table class="meta">
<tr><td>{{ t.when }}</td><td>{{ when }}</td></tr>
{% if m.place %}<tr><td>{{ t.where }}</td><td>{{ m.place }}</td></tr>{% endif %}
</table>
{% if m.intro %}<p class="desc">{{ m.intro }}</p>{% endif %}
<h2>{{ t.agenda }}</h2>
<ol class="agenda">
{% for i in items %}<li><strong>{{ i.title }}</strong>
{% if i.description %}<div class="desc">{{ i.description }}</div>{% endif %}</li>
{% endfor %}</ol>
<p class="small">{{ t.issued }} {{ issued }}</p>
</body></html>"""
)

_MINUTES = _env.from_string(
    """<!doctype html><html lang="{{ lang }}"><head><meta charset="utf-8">
<style>{{ style }}</style></head><body>
<div class="club">{{ club }}</div>
<h1>{{ t.minutes }}: {{ m.title }}</h1>
<table class="meta">
<tr><td>{{ t.when }}</td><td>{{ when }}</td></tr>
{% if m.place %}<tr><td>{{ t.where }}</td><td>{{ m.place }}</td></tr>{% endif %}
{% if m.chair %}<tr><td>{{ t.chair }}</td><td>{{ m.chair }}</td></tr>{% endif %}
{% if m.minute_taker %}<tr><td>{{ t.taker }}</td><td>{{ m.minute_taker }}</td></tr>{% endif %}
<tr><td>{{ t.present }}</td><td>{{ present|length }}{% if m.quorum %} ({{ t.quorum }} {{ m.quorum }}: {{ t.yes if present|length >= m.quorum else t.no }}){% endif %}</td></tr>
</table>
<h2>{{ t.agenda }}</h2>
{% for i in items %}
<h2>{{ loop.index }}. {{ i.title }}</h2>
{% if i.minutes %}<div class="min">{{ i.minutes }}</div>{% endif %}
{% if i.poll_id and i.poll_id in polls %}{% set p = polls[i.poll_id] %}
<div class="vote">{{ t.vote }}: {{ p.question }}
<table>{% for o in p.options %}<tr><td>{{ o.label }}</td><td>{{ o.poll_votes|length }}</td></tr>{% endfor %}</table></div>
{% endif %}
{% if i.decision %}<div class="decision"><strong>{{ t.decision }}:</strong> {{ i.decision }}</div>{% endif %}
{% endfor %}
<h2>{{ t.attendees }} ({{ present|length }})</h2>
<p class="small">{{ present|join(", ") }}</p>
<table class="sign"><tr><td>{{ t.chair }}</td><td>{{ t.taker }}</td></tr></table>
<p class="small">{{ t.issued }} {{ issued }}{% if not m.closed_at %} · {{ t.draft }}{% endif %}</p>
</body></html>"""
)

_TEXTS = {
    "de": {
        "invitation": "Einladung",
        "minutes": "Protokoll",
        "when": "Datum",
        "where": "Ort",
        "agenda": "Traktanden",
        "chair": "Vorsitz",
        "taker": "Protokoll",
        "present": "Anwesend",
        "quorum": "beschlussfähig ab",
        "yes": "ja",
        "no": "nein",
        "vote": "Abstimmung",
        "decision": "Beschluss",
        "attendees": "Anwesende",
        "issued": "Erstellt am",
        "draft": "Entwurf",
    },
    "en": {
        "invitation": "Invitation",
        "minutes": "Minutes",
        "when": "Date",
        "where": "Place",
        "agenda": "Agenda",
        "chair": "Chair",
        "taker": "Minutes",
        "present": "Present",
        "quorum": "quorum",
        "yes": "reached",
        "no": "not reached",
        "vote": "Vote",
        "decision": "Decision",
        "attendees": "Present",
        "issued": "Created on",
        "draft": "draft",
    },
}


def _lang(lang: str | None) -> str:
    return "de" if (lang or "de").lower().startswith("de") else "en"


def _when(dt: datetime, lang: str) -> str:
    """The meeting's date and time in Swiss time."""
    from zoneinfo import ZoneInfo

    from hubra.core.services.mail_format import mail_date

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(ZoneInfo("Europe/Zurich"))
    return f"{mail_date(local.date(), lang)}, {local:%H:%M}"


def _render(template, **ctx) -> bytes:
    from weasyprint import HTML

    from hubra.core.services.email import club_display_name
    from hubra.core.services.qr_bill import _no_fetch

    lang = ctx.pop("lang")
    html = template.render(
        style=_STYLE,
        club=club_display_name(),
        lang=lang,
        t=_TEXTS[lang],
        issued=datetime.now(timezone.utc).strftime(
            "%d.%m.%Y" if lang == "de" else "%Y-%m-%d"
        ),
        **ctx,
    )
    return HTML(string=html, url_fetcher=_no_fetch()).write_pdf()


def invitation(meeting, items, lang: str | None) -> bytes:
    lang = _lang(lang)
    return _render(
        _INVITATION,
        lang=lang,
        m=meeting,
        items=items,
        when=_when(meeting.starts_at, lang),
    )


def minutes(meeting, items, present: list[str], polls: dict, lang: str | None) -> bytes:
    lang = _lang(lang)
    return _render(
        _MINUTES,
        lang=lang,
        m=meeting,
        items=items,
        present=present,
        polls=polls,
        when=_when(meeting.starts_at, lang),
    )
