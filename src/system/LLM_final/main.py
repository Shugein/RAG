from __future__ import annotations
from typing import List, Literal, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from dateutil import tz
from pathlib import Path
from src.system.LLM_final.output import save_article_pdf
from src.system.LLM_final.sys_prompt import SYSTEM_PROMPT
import os
import json
from dotenv import load_dotenv

from openai import OpenAI

load_dotenv()

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
OPENAI_API_KEY = os.environ.get('API_KEY_2')
client = OpenAI(api_key=OPENAI_API_KEY)

# Заводим типы новостей, которые необходимы для формирования черновика, например, слухи имеют низкую достоверность
# поэтому черновик для такой новости надо писать аккуратно
NewsType = Literal[
    "earnings", "guidance", "mna", "default_bankruptcy", "rating_action",
    "regulatory_sanctions", "macro", "social_buzz", "crisis_systemic",
    "tech_fintech", "industry_trend", "rumor_leak", "people_social"
]

# Определеяем формат вывода черновика
OutputFormat = Literal[
    "alert", "social_post", "article_draft", "digest", "timeline", "scenario_table",
    "graph_connections", "explainer_post", "longread", "infographic_post"
]

# Определеяем финансовые инструменты исходя из новости
InstrumentClass = Literal[
    "equity", "etf", "bond", "fx", "crypto", "commodity", "index", "rate_future", "other"
]

# Используется для передачи агенту для генерации черновика, пример использования:
# model_forecasts={
#     "TSLA": Forecast(
#         horizon="1d",
#         direction="down",
#         expected_move_pct=2.3,
#         confidence=0.62,
#         notes="Реакция на сжатие маржи; высокая волатильность"
#     )
# }
class Forecast(BaseModel):
    # прогноз вашей модели по конкретному инструменту
    horizon: str = Field(..., description="Напр. '1d', '1w'")
    direction: Literal["up", "down", "neutral"]
    expected_move_pct: Optional[float] = Field(None, description="Прогноз изменения, % от текущей цены")
    confidence: Optional[float] = Field(None, description="Уверенность модели [0..1]")
    notes: Optional[str] = None

# Описание финансового инструмента, пример использования:
# instruments=[Instrument(ticker="TSLA", name="Tesla Inc.", class_="equity", exchange="NASDAQ", currency="USD", country="US")],
class Instrument(BaseModel):
    # Название тикера
    ticker: str
    # Название финансового инструмента
    name: Optional[str] = None
    class_: InstrumentClass = Field("equity", alias="class")
    # Код биржа
    exchange: Optional[str] = None
    # Валюта котировки
    currency: Optional[str] = None
    # Страна листинга
    country: Optional[str] = None

# Описывает источник новости
class SourceItem(BaseModel):
    # Заголовок статьи из источника
    title: Optional[str] = None
    # Ссылка на источник
    url: Optional[str] = None

# Входной формат черновика для LLM
class DraftRequest(BaseModel):
    # Тип новости
    news_type: NewsType
    language: Literal["ru", "en"] = "ru"
    # Тип аудитории, где pro наиболее продвинутые читатели
    audience: Literal["retail", "pro", "mixed"] = "mixed"
    # Определяем тональность черновика:
    # concise(телеграфный)
    # explanatory(поясняющий)
    # urgent(срочный)
    # bullish / bearish(смещённый тон при наличии сигнала)
    tone: Literal["neutral", "concise", "explanatory", "urgent", "bullish", "bearish"] = "neutral"
    timezone: str = "Europe/Riga"

    headline: Optional[str] = None              # заголовок исходной новости
    summary: Optional[str] = None               # краткое описание/выжимка
    body_text: Optional[str] = None             # текст исходной заметки (если есть)
    sources: List[SourceItem] = Field(default_factory=list) # список источников (IR, СМИ, регулятор) для цитирования/комплаенса.

    # набор инструментов (тикер/биржа/валюта/страна) для правильных упоминаний и хэштегов
    instruments: List[Instrument] = Field(default_factory=list)
    model_forecasts: Dict[str, Forecast] = Field(default_factory=dict)

    # какие форматы генерировать (alert/social/article/digest/...)
    desired_outputs: List[OutputFormat] = Field(default_factory=lambda: ["social_post", "article_draft"])
    # добавлять хэштеги по тикерам/темам
    include_hashtags: bool = True
    # вставить обязательные дисклеймеры
    include_disclaimer: bool = True
    # генерировать идеи графиков/инфографики для редактора.
    include_visual_ideas: bool = True

    # дополнительные настройки
    max_words_social: int = 280
    max_words_article: int = 500
    # внутренний приоритет новости [0..1]: можно усиливать «urgent» стиль, сортировку блоков, частоту эмодзи/алертов
    hot_score: Optional[float] = None

# Финальный вариант, который должен прислать агент openai
class DraftResponse(BaseModel):
    # финальный заголовок материала
    headline: str
    # короткая выжимка под заголовком
    dek: Optional[str] = None
    # форматы текста (для соцсетей, статьи и тд)
    variants: Dict[str, str]
    # суть новости в виде тегов
    key_points: List[str]
    # хэштеги для соцсетей
    hashtags: Optional[List[str]] = None
    # идеи визуализации
    visualization_ideas: Optional[List[str]] = None
    # флаги дисклеймера
    compliance_flags: List[str]
    # наличие дисклеймера
    disclaimer: Optional[str] = None
    # технические данные
    sources: List[SourceItem]
    metadata: Dict[str, Any]

def render_user_prompt(payload: DraftRequest) -> str:
    # Преобразуем вход в компактный JSON для модели
    # (модель увидит и тип новости, и прогнозы, и желаемые форматы).
    as_dict = json.loads(payload.model_dump_json(by_alias=True, exclude_none=False))
    return (
        "Сгенерируй черновики по следующему заданию.\n"
        "Отдай СТРОГО один JSON-объект, соответствующий полям DraftResponse.\n"
        "Внимание: поля 'variants' заполни только теми форматами, которые запрошены в desired_outputs.\n"
        "Включи 'compliance_flags' (например: ['no_investment_advice', 'source_cited']).\n\n"
        f"INPUT_JSON:\n{json.dumps(as_dict, ensure_ascii=False)}"
    )


def generate_news_draft(payload: DraftRequest) -> DraftResponse:
    """
    Основная функция: вызывает OpenAI и возвращает типизированный DraftResponse.
    """
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не задан. Установите переменную окружения.")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": render_user_prompt(payload)}
    ]

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        response_format={"type": "json_object"},
    )

    raw = completion.choices[0].message.content
    data = json.loads(raw)

    # Обогащаем метаданные (время генерации, модель и пр.)
    now_riga = datetime.now(tz.gettz(payload.timezone)).isoformat()
    data.setdefault("metadata", {})
    data["metadata"].update({
        "generated_at": now_riga,
        "model": OPENAI_MODEL,
        "news_type": payload.news_type,
        "language": payload.language,
        "audience": payload.audience,
        "tone": payload.tone,
        "desired_outputs": payload.desired_outputs,
        "hot_score": payload.hot_score,
    })

    return DraftResponse(**data)

if __name__ == "__main__":
    example = DraftRequest(
        news_type="earnings",
        language="ru",
        audience="mixed",
        tone="explanatory",
        headline="Tesla: EPS ниже ожиданий, выручка близка к консенсусу",
        summary="Компания отчиталась за 3К25: EPS ниже консенсуса на 8%, маржа под давлением, поставки на уровне ориентира.",
        sources=[SourceItem(title="Company IR", url="https://ir.tesla.com/"), SourceItem(url="https://www.wsj.com/")],
        instruments=[Instrument(ticker="TSLA", name="Tesla Inc.", class_="equity", exchange="NASDAQ", currency="USD", country="US")],
        model_forecasts={"TSLA": Forecast(horizon="1d", direction="down", expected_move_pct=2.3, confidence=0.62, notes="Реакция на маржу; риск волатильности высок.")},
        desired_outputs=["social_post", "article_draft", "alert"],
        include_hashtags=True,
        include_disclaimer=True,
        include_visual_ideas=True,
        max_words_social=280,
        max_words_article=500,
        hot_score=0.78)

    draft = generate_news_draft(example)
    draft_dict = draft.model_dump(by_alias=True)
    pdf_path = save_article_pdf(draft_dict, "article.pdf")

    print(f"PDF сохранён: {Path(pdf_path).resolve()}")