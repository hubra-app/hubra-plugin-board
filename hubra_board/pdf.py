"""The GV invitation and minutes as PDF, on the club's letterhead.

Hubra lays them out (``pdf.render``, docs/contracts.md "PDFs" in
hubra-app/hubra): logo, name and address on every page, contact line and
page numbers at the bottom. This module only writes the body.
"""

from __future__ import annotations

from datetime import datetime, timezone

from jinja2 import Environment, select_autoescape

_env = Environment(autoescape=select_autoescape(default=True, default_for_string=True))

# Page, fonts, h1/h2 and the colours come from the letterhead.
_STYLE = """
.board { line-height: 1.45; }
.meta { margin: 0 0 6mm; }
.meta td { padding: 0 6mm 1mm 0; vertical-align: top; }
.meta td:first-child { color: #666; }
ol.agenda { padding-left: 6mm; }
ol.agenda li { margin-bottom: 2mm; }
.desc, .min { white-space: pre-wrap; }
.desc { color: #555; }
.decision { margin-top: 1.5mm; padding: 1.5mm 3mm; border-left: 2pt solid currentColor; background: #f5f5f5; }
.vote { margin-top: 1.5mm; font-size: 9pt; }
.vote td { padding: 0 4mm 0 0; }
.sign { margin-top: 16mm; width: 100%; }
.sign td { width: 50%; padding-top: 12mm; border-top: .6pt solid #999; font-size: 9pt; color: #555; }
.sign td + td { padding-left: 8mm; }
.small { font-size: 8.5pt; color: #666; }
"""

_INVITATION = _env.from_string(
    """<style>{{ style }}</style><div class="board">
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
</div>"""
)

_MINUTES = _env.from_string(
    """<style>{{ style }}</style><div class="board">
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
</div>"""
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


def _render(template, title: str, **ctx) -> bytes:
    import base64

    from hubra.core.contracts import SYSTEM, call

    lang = ctx.pop("lang")
    body = template.render(
        style=_STYLE,
        lang=lang,
        t=_TEXTS[lang],
        issued=datetime.now(timezone.utc).strftime(
            "%d.%m.%Y" if lang == "de" else "%Y-%m-%d"
        ),
        **ctx,
    )
    # SYSTEM: the route already checked who may read the meeting.
    out = call("pdf.render", title=title[:200], body_html=body, lang=lang, actor=SYSTEM)
    return base64.b64decode(out["pdf_base64"])


def invitation(meeting, items, lang: str | None) -> bytes:
    lang = _lang(lang)
    return _render(
        _INVITATION,
        f"{_TEXTS[lang]['invitation']}: {meeting.title}",
        lang=lang,
        m=meeting,
        items=items,
        when=_when(meeting.starts_at, lang),
    )


def minutes(meeting, items, present: list[str], polls: dict, lang: str | None) -> bytes:
    lang = _lang(lang)
    return _render(
        _MINUTES,
        f"{_TEXTS[lang]['minutes']}: {meeting.title}",
        lang=lang,
        m=meeting,
        items=items,
        present=present,
        polls=polls,
        when=_when(meeting.starts_at, lang),
    )
