from __future__ import annotations
from html import escape
from typing import Dict, Any, List, Tuple
from pathlib import Path

# Маппинги "вариантов" к читаемым названиям и эмодзи
VARIANT_TITLES = {
    "article_draft": ("Черновик статьи", "📰"),
    "social_post": ("Соцпост", "✍️"),
    "alert": ("Алерт", "🔔"),
    "digest": ("Дайджест", "📊"),
    "timeline": ("Таймлайн", "🗓️"),
    "scenario_table": ("Сценарии", "📑"),
    "graph_connections": ("Граф связей", "🌐"),
    "explainer_post": ("Пояснение", "📝"),
    "longread": ("Лонгрид", "📚"),
    "infographic_post": ("Инфографика", "📈"),
}

def _nl2p(text: str) -> str:
    """Превращает многострочный текст в <p> абзацы, аккуратно экранируя HTML."""
    if not text:
        return ""
    parts = [f"<p>{escape(x.strip())}</p>" for x in text.strip().split("\n") if x.strip()]
    return "\n".join(parts)

def _list_to_ul(items: List[str]) -> str:
    if not items:
        return ""
    li = "\n".join(f"<li>{escape(x)}</li>" for x in items if str(x).strip())
    return f"<ul class='bullet'>{li}</ul>"

def _render_sources(sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "<p class='muted'>Источники не указаны</p>"
    lis = []
    for s in sources:
        title = s.get("title") or s.get("url") or "Источник"
        url = s.get("url")
        if url:
            lis.append(f"<li><a href='{escape(url)}' target='_blank' rel='noopener'>{escape(title)}</a></li>")
        else:
            lis.append(f"<li>{escape(title)}</li>")
    return f"<ul class='sources'>{''.join(lis)}</ul>"

def _render_hashtags(tags: List[str]) -> str:
    if not tags:
        return ""
    chips = "".join(f"<span class='chip'>#{escape(t.lstrip('#'))}</span>" for t in tags if str(t).strip())
    return f"<div class='tags'>{chips}</div>"

def _render_flags(flags: List[str]) -> str:
    if not flags:
        return ""
    chips = "".join(f"<span class='flag'>{escape(f)}</span>" for f in flags if str(f).strip())
    return f"<div class='flags'>{chips}</div>"

def _render_variants(variants: Dict[str, str]) -> Tuple[str, str]:
    """Возвращает HTML двух блоков:
       1) основной контент статьи (если есть article_draft),
       2) сетка карточек для остальных вариантов."""
    main_html = ""
    cards_html = []

    for key, content in variants.items():
        title, emoji = VARIANT_TITLES.get(key, (key, "🧩"))
        block = (
            f"<div class='card'>"
            f"  <div class='card-h'>{emoji} {escape(title)}</div>"
            f"  <div class='card-b'>{_nl2p(content)}</div>"
            f"</div>"
        )
        if key == "article_draft":
            main_html = block
        else:
            cards_html.append(block)

    grid_html = f"<div class='grid-cards'>{''.join(cards_html)}</div>" if cards_html else ""
    return main_html, grid_html

def render_article_html(draft: Dict[str, Any]) -> str:
    """Светлая версия: белый фон, без тёмной темы и без секции тегов/мета-бейджей."""
    headline = draft.get("headline") or "Без заголовка"
    dek = draft.get("dek") or ""
    variants = draft.get("variants") or {}
    key_points = draft.get("key_points") or []
    # ИСКЛЮЧАЕМ хэштеги целиком
    # hashtags = draft.get("hashtags") or []
    vis_ideas = draft.get("visualization_ideas") or []
    flags = draft.get("compliance_flags") or []
    disclaimer = draft.get("disclaimer") or ""
    sources = draft.get("sources") or []
    # ИСКЛЮЧАЕМ мета-теги целиком
    # meta = draft.get("metadata") or {}

    main_variant_html, other_variants_html = _render_variants(variants)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(headline)}</title>
<style>
:root {{
  --bg: #ffffff;
  --panel: #ffffff;
  --ink: #111111;
  --muted: #555555;
  --brand: #1b4fd6;
  --border: #dddddd;
  --radius: 14px;
  --maxw: 980px;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font: 16px/1.6 system-ui, -apple-system, Segoe UI, Roboto, Inter, Arial, sans-serif;
}}
.container {{ max-width: var(--maxw); margin: 40px auto; padding: 0 20px; }}
.article {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 28px;
}}
h1.title {{ font-size: 32px; line-height: 1.2; margin: 0 0 8px; }}
.dek {{ color: var(--muted); font-size: 18px; margin: 0 0 18px; }}
.section-h {{
  margin: 28px 0 12px; font-weight: 700; letter-spacing: .2px; font-size: 14px;
  text-transform: uppercase; color: #333;
}}
ul.bullet {{ margin: 0; padding-left: 18px; }}
ul.bullet li {{ margin: 6px 0; }}
.card {{
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}}
.card-h {{ font-weight: 700; margin-bottom: 8px; color: #111; font-size: 16px; }}
.card-b p {{ margin: .5em 0; }}
.grid-cards {{
  display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  margin-top: 8px;
}}
.sources a {{ color: var(--brand); text-decoration: none; }}
.sources a:hover {{ text-decoration: underline; }}
.muted {{ color: var(--muted); }}
footer.disclaimer {{
  margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border); color: #333;
}}
@media print {{
  body {{ background: #ffffff; color: #000000; }}
  .article {{ border-color: #bbbbbb; }}
}}
</style>
</head>
<body>
  <div class="container">
    <article class="article">
      <header>
        <h1 class="title">{escape(headline)}</h1>
        {"<div class='dek'>" + escape(dek) + "</div>" if dek else ""}
      </header>

      <section>
        <div class="section-h">Ключевые моменты</div>
        {"<div class='card'>" + _list_to_ul(key_points) + "</div>" if key_points else "<p class='muted'>Нет ключевых пунктов</p>"}
      </section>

      <section>
        <div class="section-h">Основной текст</div>
        {main_variant_html or "<p class='muted'>Вариант 'article_draft' не передан</p>"}
      </section>

      {"<section><div class='section-h'>Другие форматы</div>" + other_variants_html + "</section>" if other_variants_html else ""}

      {"<section><div class='section-h'>Идеи визуализаций</div><div class='card'>" + _list_to_ul(vis_ideas) + "</div></section>" if vis_ideas else ""}

      <section>
        <div class="section-h">Источники</div>
        <div class="card">{_render_sources(sources)}</div>
      </section>

      {"<section><div class='section-h'>Комплаенс</div><div class='card'>" + _render_flags(flags) + "</div></section>" if flags else ""}

      {"<footer class='disclaimer'><strong>Дисклеймер:</strong> " + escape(disclaimer) + "</footer>" if disclaimer else ""}
    </article>
  </div>
</body>
</html>
"""
    return html

def save_article_pdf(draft_dict: Dict, out_pdf: str = "article.pdf") -> str:
    """Пытается сохранить PDF через WeasyPrint; если не установлен — через Playwright/Chromium."""
    html = render_article_html(draft_dict)

    # 1) Пробуем WeasyPrint (ленивый импорт, без падения всего модуля)
    try:
        from weasyprint import HTML  # импорт только внутри функции
        HTML(string=html, base_url=str(Path.cwd())).write_pdf(out_pdf)
        return out_pdf
    except Exception as e:
        # Можно залогировать e, но не падаем — идём в Playwright
        pass

    # 2) Fallback: Playwright/Chromium
    from playwright.sync_api import sync_playwright  # pip install playwright ; playwright install chromium

    tmp_html = Path("article_tmp.html")
    tmp_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(tmp_html.resolve().as_uri(), wait_until="load")
        page.pdf(
            path=out_pdf,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
        )
        browser.close()

    tmp_html.unlink(missing_ok=True)
    return out_pdf
