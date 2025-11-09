import os
import time
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
import json


# ===== МОДЕЛИ ДАННЫХ =====
class Person(BaseModel):
    name: str = Field(description="ФИО или имя персоны")
    position: Optional[str] = Field(None, description="Должность")
    company: Optional[str] = Field(None, description="Компания")


class Company(BaseModel):
    name: str = Field(description="Название компании")
    ticker: Optional[str] = Field(None, description="Тикер акций")
    sector: Optional[str] = Field(None, description="Отрасль")


class Market(BaseModel):
    name: str = Field(description="Название рынка/биржи/индекса")
    type: str = Field(description="Тип: 'биржа', 'индекс', 'валюта', 'товар'")
    value: Optional[float] = Field(None, description="Значение/котировка")
    change: Optional[str] = Field(None, description="Изменение")


class FinancialMetric(BaseModel):
    metric_type: str = Field(description="Тип показателя")
    value: str = Field(description="Значение с единицами")
    company: Optional[str] = Field(None, description="Компания")


class ExtractedEntities(BaseModel):
    publication_date: Optional[str] = Field(None, description="Дата YYYY-MM-DD")
    people: List[Person] = Field(default_factory=list)
    companies: List[Company] = Field(default_factory=list)
    markets: List[Market] = Field(default_factory=list)
    financial_metrics: List[FinancialMetric] = Field(default_factory=list)


# ===== ГЛОССАРИЙ =====
class RussianFinanceGlossary:
    def __init__(self):
        self.companies = {
            "СБЕРБАНК": {"full_name": "ПАО Сбербанк", "ticker": "SBER"},
            "ГАЗПРОМ": {"full_name": "ПАО Газпром", "ticker": "GAZP"},
            "ЛУКОЙЛ": {"full_name": "ПАО ЛУКОЙЛ", "ticker": "LKOH"},
            "РОСНЕФТЬ": {"full_name": "ПАО Роснефть", "ticker": "ROSN"},
            "ЯНДЕКС": {"full_name": "Яндекс", "ticker": "YNDX"},
        }

        self.markets = {
            "ММВБ": {"full_name": "Московская биржа"},
            "MOEX": {"full_name": "Московская биржа"},
            "РТС": {"full_name": "Индекс РТС"},
        }

        self.terms = {
            "ЦБ РФ": "Центральный банк Российской Федерации",
            "Ключевая ставка": "Базовая процентная ставка ЦБ РФ",
            "млрд": "миллиардов",
            "трлн": "триллионов",
        }

    def get_glossary_text(self) -> str:
        """Возвращает глоссарий в текстовом формате"""
        text = "## ГЛОССАРИЙ:\n\n"

        text += "## Компании:\n"
        for abbr, info in self.companies.items():
            text += f"- {abbr}: {info['full_name']} (тикер: {info['ticker']})\n"

        text += "\n## Биржи:\n"
        for abbr, info in self.markets.items():
            text += f"- {abbr}: {info['full_name']}\n"

        text += "\n## Термины:\n"
        for abbr, full in self.terms.items():
            text += f"- {abbr}: {full}\n"

        return text


# ===== ЛОКАЛЬНЫЙ ЭКСТРАКТОР =====
class LocalFinanceNERExtractor:
    """
    Экстрактор на базе локальной модели Qwen3-4B-Instruct с 4-bit квантизацией
    Использует batch inference для максимальной скорости
    """

    def __init__(
        self,
        model_name: str = "unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
        device: str = "cuda",
        batch_size: int = 10
    ):
        self.model_name = model_name
        self.device = device
        self.batch_size = batch_size
        self.glossary = RussianFinanceGlossary()

        print(f"🔄 Загрузка модели {model_name}...")
        start = time.time()

        # Настройка 4-bit квантизации
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

        # Загрузка модели
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            quantization_config=bnb_config,
            device_map="auto",
            trust_remote_code=True,
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            trust_remote_code=True,
        )

        # Для Qwen нужно установить pad_token
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.tokenizer.pad_token_id = self.tokenizer.eos_token_id

        print(f"✅ Модель загружена за {time.time() - start:.2f} сек")
        print(f"   Устройство: {self.device}")
        print(f"   Batch size: {batch_size}")

        # Статистика
        self.stats = {
            "total_requests": 0,
            "total_time": 0.0,
            "avg_time_per_request": 0.0,
        }

    def _build_prompt(self, news_text: str) -> str:
        """Строит промпт для Qwen модели"""

        system_prompt = """Извлеки из финансовой новости следующую информацию и верни в JSON формате:

1. companies - упомянутые компании
2. people - упомянутые персоны
3. markets - биржи, индексы
4. financial_metrics - финансовые показатели (прибыль, выручка, дивиденды и т.д.)

Верни ТОЛЬКО JSON, ничего больше."""

        glossary = self.glossary.get_glossary_text()

        # Пример для few-shot обучения
        example_news = """Акции Сбербанка выросли на 3%. Глава банка Герман Греф сообщил о прибыли 100 млрд рублей."""
        example_json = """{
  "publication_date": null,
  "people": [{"name": "Герман Греф", "position": "глава банка", "company": "Сбербанк"}],
  "companies": [{"name": "Сбербанк", "ticker": "SBER", "sector": null}],
  "markets": [],
  "financial_metrics": [
    {"metric_type": "рост акций", "value": "3%", "company": "Сбербанк"},
    {"metric_type": "прибыль", "value": "100 млрд рублей", "company": "Сбербанк"}
  ]
}"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": example_news},
            {"role": "assistant", "content": example_json},
            {"role": "user", "content": news_text}
        ]

        # Формируем промпт в формате Qwen
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )

        return prompt

    def extract_entities(self, news_text: str, verbose: bool = False) -> Optional[ExtractedEntities]:
        """Извлекает сущности из одной новости"""

        prompt = self._build_prompt(news_text)

        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=4096
        ).to(self.device)

        start_time = time.time()

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=1024,
                temperature=0.1,
                do_sample=True,
                pad_token_id=self.tokenizer.pad_token_id,
            )

        elapsed = time.time() - start_time
        self.stats["total_requests"] += 1
        self.stats["total_time"] += elapsed

        # Декодируем ответ
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Извлекаем JSON из ответа
        try:
            # Ищем JSON в ответе
            if "```json" in generated_text:
                json_start = generated_text.find("```json") + 7
                json_end = generated_text.find("```", json_start)
                json_text = generated_text[json_start:json_end].strip()
            elif "{" in generated_text:
                # Ищем первый { и правильный закрывающий }
                json_start = generated_text.find("{")
                json_end = generated_text.find("}", json_start)

                # Подсчитываем скобки
                bracket_count = 0
                for idx in range(json_start, len(generated_text)):
                    if generated_text[idx] == '{':
                        bracket_count += 1
                    elif generated_text[idx] == '}':
                        bracket_count -= 1
                        if bracket_count == 0:
                            json_end = idx + 1
                            break

                json_text = generated_text[json_start:json_end]
            else:
                raise ValueError("JSON не найден в ответе")

            if verbose:
                print(f"\n{'='*60}")
                print("СЫРОЙ ОТВЕТ МОДЕЛИ:")
                print(json_text)
                print(f"{'='*60}\n")

            entities = ExtractedEntities.model_validate_json(json_text)
            return entities

        except Exception as e:
            if verbose:
                print(f"Ошибка парсинга: {e}")
                print(f"Ответ модели: {generated_text[:500]}")
            return None

    def extract_entities_batch(self, news_list: List[str], verbose: bool = False) -> List[Optional[ExtractedEntities]]:
        """Batch обработка новостей по batch_size штук"""

        results = []
        total_batches = (len(news_list) + self.batch_size - 1) // self.batch_size

        for batch_idx in range(total_batches):
            start_idx = batch_idx * self.batch_size
            end_idx = min(start_idx + self.batch_size, len(news_list))
            batch = news_list[start_idx:end_idx]

            print(f"📦 Batch {batch_idx + 1}/{total_batches}: обработка {len(batch)} новостей...")

            # Подготавливаем промпты для всего batch
            prompts = [self._build_prompt(news) for news in batch]

            # Токенизируем с padding
            inputs = self.tokenizer(
                prompts,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=4096
            ).to(self.device)

            start_time = time.time()

            # Генерируем для всего batch сразу
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=1024,
                    temperature=0.1,
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                )

            elapsed = time.time() - start_time
            print(f"   ✅ Batch завершен за {elapsed:.2f} сек ({elapsed/len(batch):.2f} сек/новость)")

            self.stats["total_requests"] += len(batch)
            self.stats["total_time"] += elapsed

            # Декодируем и парсим результаты
            for i, output in enumerate(outputs):
                generated_text = self.tokenizer.decode(output, skip_special_tokens=True)

                try:
                    # Извлекаем JSON
                    if "```json" in generated_text:
                        json_start = generated_text.find("```json") + 7
                        json_end = generated_text.find("```", json_start)
                        json_text = generated_text[json_start:json_end].strip()
                    elif "{" in generated_text:
                        # Ищем первый { и последний }
                        json_start = generated_text.find("{")
                        json_end = generated_text.find("}", json_start)

                        # Подсчитываем скобки для нахождения правильного закрывающего }
                        bracket_count = 0
                        for idx in range(json_start, len(generated_text)):
                            if generated_text[idx] == '{':
                                bracket_count += 1
                            elif generated_text[idx] == '}':
                                bracket_count -= 1
                                if bracket_count == 0:
                                    json_end = idx + 1
                                    break

                        json_text = generated_text[json_start:json_end]
                    else:
                        raise ValueError("JSON не найден")

                    if verbose:
                        print(f"\nНовость {start_idx + i + 1}:")
                        print(json_text[:200] + "...")

                    entities = ExtractedEntities.model_validate_json(json_text)
                    results.append(entities)

                except Exception as e:
                    if verbose:
                        print(f"Ошибка в новости {start_idx + i + 1}: {e}")
                    results.append(None)

        return results

    def print_stats(self):
        """Выводит статистику обработки"""
        avg_time = self.stats["total_time"] / self.stats["total_requests"] if self.stats["total_requests"] > 0 else 0

        print("\n" + "="*60)
        print("📊 СТАТИСТИКА ОБРАБОТКИ (ЛОКАЛЬНАЯ МОДЕЛЬ)")
        print("="*60)
        print(f"Модель: {self.model_name}")
        print(f"Всего запросов: {self.stats['total_requests']}")
        print(f"Общее время: {self.stats['total_time']:.2f} сек")
        print(f"Среднее время/запрос: {avg_time:.2f} сек")
        print(f"Скорость: {1/avg_time:.2f} новостей/сек" if avg_time > 0 else "N/A")
        print("="*60)


# ===== ПРИМЕР ИСПОЛЬЗОВАНИЯ =====
def main():
    # Инициализация локального экстрактора
    extractor = LocalFinanceNERExtractor(
        model_name="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
        device="cuda",
        batch_size=10  # Обрабатываем по 10 новостей за раз
    )

    # Примеры новостей
    news_samples = [
        """Акции Сбербанка выросли на 3.2% после публикации отчетности.
        Чистая прибыль составила 389 млрд рублей. Глава Сбербанка Герман Греф
        заявил о планах увеличить дивиденды.""",

        """Индекс ММВБ закрылся на отметке 3245 пунктов (+1.5%).
        На фоне роста цен на нефть выросли акции Лукойла (+2.1%) и Роснефти (+1.8%).""",

        """ЦБ РФ повысил ключевую ставку до 16%. Аналитики ВТБ Капитал
        ожидают замедления инфляции в следующем квартале.""",

        """Яндекс представил квартальную отчетность. Выручка составила
        150 млрд рублей (+18% год к году). Акции выросли на 5%.""",

        """Газпром объявил о рекордных дивидендах в размере 52 рублей на акцию.
        Аналитики повысили целевую цену до 250 рублей."""
    ]

    print("\n🚀 Начинаем BATCH обработку новостей локальной моделью...\n")
    print(f"Количество новостей: {len(news_samples)}")
    print(f"Batch size: {extractor.batch_size}\n")

    VERBOSE = True

    start_time = time.time()

    # BATCH обработка
    results = extractor.extract_entities_batch(news_samples, verbose=VERBOSE)

    elapsed = time.time() - start_time
    print(f"\n✅ Обработка завершена за {elapsed:.2f} секунд")
    print(f"   Скорость: {len(news_samples)/elapsed:.2f} новостей/сек\n")

    # Выводим результаты
    for i, (news, entities) in enumerate(zip(news_samples, results), 1):
        print(f"\n{'='*70}")
        print(f"📰 НОВОСТЬ {i}/{len(news_samples)}")
        print(f"{'='*70}")
        print(f"ТЕКСТ:\n{news}\n")

        if entities is None:
            print(f"   ✗ ОШИБКА: Не удалось обработать")
        else:
            print(f"✓ ИЗВЛЕЧЕНО:")
            print(f"  • Компаний: {len(entities.companies)}")
            for c in entities.companies:
                print(f"    - {c.name}" + (f" ({c.ticker})" if c.ticker else ""))
            print(f"  • Персон: {len(entities.people)}")
            for p in entities.people:
                print(f"    - {p.name}" + (f", {p.position}" if p.position else ""))
            print(f"  • Рынков: {len(entities.markets)}")
            for m in entities.markets:
                print(f"    - {m.name}: {m.value} ({m.change})" if m.value else f"    - {m.name}")
            print(f"  • Метрик: {len(entities.financial_metrics)}")
            for fm in entities.financial_metrics:
                print(f"    - {fm.metric_type}: {fm.value}")

    print(f"\n{'='*70}")

    # Статистика
    extractor.print_stats()

    # Оценка для 1000 новостей
    time_per_1000 = (elapsed / len(news_samples)) * 1000
    print(f"\n💡 ОЦЕНКА ДЛЯ 1000 НОВОСТЕЙ:")
    print(f"   Примерное время: {time_per_1000/60:.1f} минут")
    print(f"   Стоимость: $0 (локальная модель)")


if __name__ == "__main__":
    main()
