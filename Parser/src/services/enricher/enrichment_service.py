# src/services/enricher/enrichment_service.py
"""
Сервис обогащения новостей с AI-based NER extraction
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import News, Entity, LinkedCompany, Topic
# Заменяем старый NER на AI extraction
# from src.services.enricher.ner_extractor import NERExtractor
from entity_recognition import CachedFinanceNERExtractor  # GPT-5 API
from entity_recognition_local import LocalFinanceNERExtractor  # Qwen3-4B local
from src.services.enricher.moex_linker import MOEXLinker
from src.services.enricher.topic_classifier import TopicClassifier
from src.services.outbox.publisher import EventPublisher
from src.services.impact_calculator import ImpactCalculator
from src.services.covariance_service import CovarianceService
from src.services.events.ceg_realtime_service import CEGRealtimeService
from src.core.config import settings

logger = logging.getLogger(__name__)


class EnrichmentService:
    """
    Главный сервис обогащения, координирующий работу всех компонентов
    Использует AI-based NER (GPT-5/Qwen) для извлечения сущностей
    """

    def __init__(self, session: AsyncSession, use_local_ai: bool = False):
        self.session = session

        # AI NER extraction (dual-pass: Qwen быстро → GPT-5 верификация)
        self.use_local_ai = use_local_ai
        if use_local_ai:
            logger.info("Initializing LOCAL AI NER (Qwen3-4B)")
            self.ai_ner = LocalFinanceNERExtractor(
                model_name="unsloth/Qwen3-4B-Instruct-2507-unsloth-bnb-4bit",
                device="cuda",
                batch_size=5
            )
        else:
            logger.info("Initializing GPT-5 AI NER (OpenAI API)")
            api_key = os.getenv("API_KEY_2") or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.warning("No API key found, falling back to local AI")
                self.ai_ner = LocalFinanceNERExtractor()
                self.use_local_ai = True
            else:
                self.ai_ner = CachedFinanceNERExtractor(
                    api_key=api_key,
                    model="gpt-4o-mini",  # или gpt-5-nano-2025-08-07
                    enable_caching=True
                )

        self.moex_linker = MOEXLinker(enable_auto_learning=True)
        self.topic_classifier = TopicClassifier()
        self.event_publisher = EventPublisher(session)
        self.impact_calculator = ImpactCalculator()
        self.covariance_service = CovarianceService()

        # CEG real-time service (будет инициализирован позже с graph_service)
        self.ceg_service: Optional[CEGRealtimeService] = None

        self._initialized = False
    
    async def initialize(self):
        """Инициализация сервиса"""
        if not self._initialized:
            await self.moex_linker.initialize()
            await self.topic_classifier.initialize()
            await self.impact_calculator.initialize()
            await self.covariance_service.initialize()

            # Инициализируем CEG service если есть graph
            if self.topic_classifier.graph:
                self.ceg_service = CEGRealtimeService(
                    session=self.session,
                    graph_service=self.topic_classifier.graph,
                    lookback_window=30  # 30 дней для ретроспективного анализа
                )
                logger.info("CEG real-time service initialized")

            self._initialized = True
    
    async def enrich_news_batch(self, news_list: List[str], news_metadata: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Batch обогащение массива новостей через новый NER
        
        Args:
            news_list: Список текстов новостей
            news_metadata: Метаданные для каждой новости
            
        Returns:
            Результат batch обработки в формате BatchExtractedEntities
        """
        logger.info(f"Starting batch enrichment of {len(news_list)} news items")
        
        try:
            # Используем новый batch метод
            batch_result = self.ai_ner.extract_entities_json_batch(
                news_list, 
                news_metadata or [], 
                verbose=True
            )
            
            logger.info(f"Batch enrichment completed: {batch_result['total_processed']}/{len(news_list)} processed")
            
            # Дополнительная статистика
            ad_count = sum(1 for item in batch_result.get('news_items', []) 
                          if item and item.get('is_advertisement', False))
            financial_count = sum(1 for item in batch_result.get('news_items', []) 
                                  if item and 'financial' in item.get('content_types', []))
            
            logger.info(f"Batch stats: {ad_count} advertisements, {financial_count} financial items")
            
            return batch_result
            
        except Exception as e:
            logger.error(f"Failed batch enrichment: {e}")
            return {
                "news_items": [],
                "total_processed": 0,
                "batch_id": None,
                "error": str(e)
            }

    async def enrich_news(self, news: News) -> Dict[str, Any]:
        """
        Полное обогащение новости
        
        Args:
            news: Объект новости
            
        Returns:
            Словарь с результатами обогащения
        """
        # Инициализируем если нужно
        await self.initialize()
        
        enrichment = {
            "entities": [],
            "companies": [],
            "topics": []
        }
        
        try:
            # Объединяем заголовок и текст для анализа
            full_text = f"{news.title}\n{news.text_plain or ''}"

            # 1. Извлекаем сущности через AI (GPT-5/Qwen)
            logger.info(f"Extracting entities from news {news.id} using AI NER")
            if hasattr(self.ai_ner, 'extract_entities_async'):
                ai_extracted = await self.ai_ner.extract_entities_async(full_text, verbose=False)
            else:
                ai_extracted = self.ai_ner.extract_entities(full_text, verbose=False)

            # Преобразуем AI extraction в сущности для БД
            # People → PERSON
            for person in ai_extracted.people:
                entity = Entity(
                    id=uuid4(),
                    news_id=news.id,
                    type="PERSON",
                    text=person.name,
                    norm={"position": person.position, "company": person.company},
                    start_pos=0,  # AI не возвращает позиции
                    end_pos=0,
                    confidence=0.9
                )
                self.session.add(entity)
                enrichment["entities"].append({
                    "type": "PERSON",
                    "text": person.name,
                    "normalized": entity.norm,
                    "confidence": 0.9
                })

            # Financial metrics
            for metric in ai_extracted.financial_metrics:
                entity = Entity(
                    id=uuid4(),
                    news_id=news.id,
                    type="FINANCIAL_METRIC",
                    text=metric.value,
                    norm={"metric_type": metric.metric_type, "company": metric.company},
                    start_pos=0,
                    end_pos=0,
                    confidence=0.9
                )
                self.session.add(entity)
                enrichment["entities"].append({
                    "type": "FINANCIAL_METRIC",
                    "text": metric.value,
                    "normalized": entity.norm,
                    "confidence": 0.9
                })

            # Markets
            for market in ai_extracted.markets:
                entity = Entity(
                    id=uuid4(),
                    news_id=news.id,
                    type="MARKET",
                    text=market.name,
                    norm={"type": market.type, "value": market.value, "change": market.change},
                    start_pos=0,
                    end_pos=0,
                    confidence=0.9
                )
                self.session.add(entity)
                enrichment["entities"].append({
                    "type": "MARKET",
                    "text": market.name,
                    "normalized": entity.norm,
                    "confidence": 0.9
                })

            # 2. Companies → линкуем к MOEX через существующий linker
            for company in ai_extracted.companies:
                # Сохраняем как сущность ORG
                entity = Entity(
                    id=uuid4(),
                    news_id=news.id,
                    type="ORG",
                    text=company.name,
                    norm={"ticker": company.ticker, "sector": company.sector},
                    start_pos=0,
                    end_pos=0,
                    confidence=0.9
                )
                self.session.add(entity)

                enrichment["entities"].append({
                    "type": "ORG",
                    "text": company.name,
                    "normalized": entity.norm,
                    "confidence": 0.9
                })

                # Линкуем к MOEX через существующий код
                if settings.ENABLE_ENRICHMENT:
                    try:
                        # Проверяем, не является ли это регуляторным органом
                        if self._is_regulatory_organization(company.name, full_text):
                            logger.debug(f"Skipping regulatory organization: {company.name}")
                            # Добавляем как регуляторную сущность, но не как компанию
                            enrichment["entities"].append({
                                "type": "REGULATORY",
                                "text": company.name,
                                "normalized": None,
                                "confidence": 0.9
                            })
                        else:
                            company_data = await self.moex_linker.link_organization(company.name)

                            if company_data and company_data.ticker:
                                linked = LinkedCompany(
                                    id=uuid4(),
                                    news_id=news.id,
                                    entity_id=entity.id,
                                    secid=company_data.ticker,
                                    isin=company_data.isin,
                                    board=company_data.board,
                                    name=company_data.company_name,
                                    confidence=company_data.confidence,
                                    is_traded=company_data.is_traded,
                                    match_method=company_data.match_method
                                )
                                self.session.add(linked)

                                enrichment["companies"].append({
                                    "secid": linked.secid,
                                    "name": linked.name,
                                    "confidence": linked.confidence,
                                    "is_traded": linked.is_traded,
                                    "ai_ticker": company.ticker  # Тикер от AI для сверки
                                })
                    except Exception as e:
                        logger.debug(f"Failed to link organization {company.name}: {e}")
                        # Продолжаем с следующей сущностью

            # Сохраняем AI extraction для дальнейшего использования
            enrichment["ai_extracted"] = ai_extracted
            
            # Добавляем новые поля для системы событий (убрана якорность)
            enrichment["event_types"] = ai_extracted.event_types if hasattr(ai_extracted, 'event_types') else []
            enrichment["ceg_flags"] = {
                "requires_market_data": ai_extracted.requires_market_data if hasattr(ai_extracted, 'requires_market_data') else False,
                "urgency_level": ai_extracted.urgency_level if hasattr(ai_extracted, 'urgency_level') else "normal",
                "confidence_score": ai_extracted.confidence_score if hasattr(ai_extracted, 'confidence_score') else 0.8
            }
            # Фильтры и категоризация (новые поля)
            enrichment["is_advertisement"] = ai_extracted.is_advertisement if hasattr(ai_extracted, 'is_advertisement') else False
            enrichment["content_types"] = ai_extracted.content_types if hasattr(ai_extracted, 'content_types') else []
            enrichment["sector"] = ai_extracted.sector if hasattr(ai_extracted, 'sector') else None
            enrichment["country"] = ai_extracted.country if hasattr(ai_extracted, 'country') else None
            
            # 3. Классифицируем по темам (упрощенная версия)
            try:
                # Простая классификация по ключевым словам
                topics = self._simple_topic_classification(full_text)
                
                for topic_name, confidence in topics:
                    topic = Topic(
                        id=uuid4(),
                        news_id=news.id,
                        topic=topic_name,
                        confidence=confidence
                    )
                    self.session.add(topic)
                    
                    enrichment["topics"].append({
                        "topic": topic_name,
                        "confidence": confidence
                    })
            except Exception as e:
                logger.debug(f"Topic classification failed: {e}")
                # Продолжаем без классификации тем
            
            # 4. Классифицируем новость и создаем события
            try:
                news_classification = self._classify_news_type(full_text, enrichment.get("companies", []))
                enrichment["news_classification"] = news_classification
                
                # Создаем событие для рыночных новостей
                if news_classification["type"] == "market":
                    event_id = await self._create_market_event(news, news_classification)
                    if event_id:
                        enrichment["event_id"] = event_id
                        
            except Exception as e:
                logger.debug(f"Event creation failed: {e}")
            
            # 5. Записываем в графовую базу данных
            try:
                await self._write_to_graph(news, enrichment)
            except Exception as e:
                logger.error(f"Failed to write to graph for news {news.id}: {e}")
                # Продолжаем без записи в граф
            
            # 6. Рассчитываем влияние на компании (асинхронно)
            try:
                if enrichment.get("companies"):
                    company_ids = [f"moex:{comp['secid']}" for comp in enrichment["companies"]]
                    
                    # Запускаем расчет влияния в фоне
                    asyncio.create_task(
                        self._calculate_impact_async(news.id, company_ids, news.published_at)
                    )
                    
                    # Запускаем обновление корреляций в фоне
                    asyncio.create_task(
                        self._update_correlations_async(company_ids)
                    )
                    
            except Exception as e:
                logger.debug(f"Impact calculation setup failed: {e}")
            
            # 7. Публикуем событие обогащения
            await self.event_publisher.publish_news_created(news, enrichment)

            # 8. CEG Real-time Processing - Построение графа событий
            if self.ceg_service and settings.ENABLE_ENRICHMENT:
                try:
                    logger.info(f"Processing CEG for news {news.id}")

                    ceg_result = await self.ceg_service.process_news(news, ai_extracted)

                    enrichment["ceg"] = {
                        "events": len(ceg_result["events"]),
                        "causal_links": len(ceg_result["causal_links"]),
                        "impacts": len(ceg_result["impacts"]),
                        "retroactive_links": ceg_result["retroactive_links"]
                    }

                    logger.info(
                        f"CEG processed for news {news.id}: "
                        f"{len(ceg_result['events'])} events, "
                        f"{len(ceg_result['causal_links'])} causal links, "
                        f"{len(ceg_result['impacts'])} market impacts, "
                        f"{ceg_result['retroactive_links']} retroactive updates"
                    )

                except Exception as e:
                    logger.error(f"CEG processing failed for news {news.id}: {e}", exc_info=True)
                    enrichment["ceg"] = {"error": str(e)}

            logger.info(
                f"Enriched news {news.id}: "
                f"{len(enrichment['entities'])} entities, "
                f"{len(enrichment['companies'])} companies, "
                f"{len(enrichment['topics'])} topics"
            )
            
        except Exception as e:
            logger.error(f"Failed to enrich news {news.id}: {e}")
            raise
        
        return enrichment
    
    def _simple_topic_classification(self, text: str) -> List[tuple]:
        """Простая классификация по ключевым словам"""
        
        text_lower = text.lower()
        topics = []
        
        # Финансовые темы
        if any(word in text_lower for word in ["прибыль", "убыток", "выручка", "earnings", "revenue", "финансы"]):
            topics.append(("финансы", 0.8))
        
        if any(word in text_lower for word in ["акции", "shares", "equity", "тикер", "бирж"]):
            topics.append(("акции", 0.7))
        
        if any(word in text_lower for word in ["облигации", "bonds", "долг", "кредит"]):
            topics.append(("облигации", 0.7))
        
        # Рыночные темы
        if any(word in text_lower for word in ["рынок", "market", "индекс", "index", "торги"]):
            topics.append(("рынок", 0.8))
        
        if any(word in text_lower for word in ["нефть", "oil", "газ", "gas", "энергия"]):
            topics.append(("энергетика", 0.8))
        
        if any(word in text_lower for word in ["банк", "bank", "кредит", "credit"]):
            topics.append(("банки", 0.8))
        
        # Технологии
        if any(word in text_lower for word in ["технологии", "tech", "ии", "ai", "цифр"]):
            topics.append(("технологии", 0.7))
        
        # Регулирование
        if any(word in text_lower for word in ["цб", "регулятор", "санкции", "санкции", "закон"]):
            topics.append(("регулирование", 0.9))
        
        return topics
    
    def _is_regulatory_organization(self, org_name: str, context: str) -> bool:
        """Проверяет, является ли организация регуляторным органом"""
        
        org_lower = org_name.lower().strip()
        context_lower = context.lower()
        
        # Список регуляторных органов и их вариантов
        regulatory_patterns = {
            # Центральный банк
            "цб": ["цб", "центральный банк", "банк россии", "цб рф", "central bank"],
            "минфин": ["минфин", "министерство финансов", "мф", "ministry of finance"],
            "фнс": ["фнс", "налоговая", "федеральная налоговая служба"],
            "фас": ["фас", "антимонопольная", "федеральная антимонопольная служба"],
            "роспотребнадзор": ["роспотребнадзор", "потребнадзор"],
            "цбк": ["цбк", "целлюлозно-бумажный комбинат"],  # Исключение для ЦБК
        }
        
        # Проверяем точные совпадения
        for regulatory, patterns in regulatory_patterns.items():
            for pattern in patterns:
                if pattern in org_lower:
                    # Дополнительная проверка контекста для ЦБ
                    if regulatory == "цб":
                        # Если в контексте есть слова о банковской деятельности, то это ЦБ
                        bank_context = any(word in context_lower for word in [
                            "банк", "банковск", "денежн", "кредитн", "ставк", "процент",
                            "инфляц", "валют", "рубл", "доллар", "евро", "регулирован"
                        ])
                        if bank_context:
                            return True
                        # Если есть упоминание ЦБК в контексте, то это не ЦБ
                        if "цбк" in context_lower or "целлюлозно" in context_lower:
                            return False
                    
                    # Для Минфина проверяем контекст о финансах
                    elif regulatory == "минфин":
                        finance_context = any(word in context_lower for word in [
                            "финанс", "бюджет", "налог", "ндс", "государственн", "казн"
                        ])
                        if finance_context:
                            return True
                    
                    # Для остальных - простое совпадение
                    else:
                        return True
        
        return False
    
    def _get_sector_for_ticker(self, ticker: str) -> Optional[str]:
        """Получить сектор по тикеру"""
        # Импортируем MOEXSectorMapper из moex_linker
        from src.services.enricher.moex_linker import MOEXSectorMapper
        return MOEXSectorMapper.get_sector(ticker)
    
    def _get_sector_name(self, sector_key: str) -> str:
        """Получить читаемое название сектора"""
        sector_names = {
            "oil_gas": "Нефть и газ",
            "metals": "Металлы и добыча",
            "banks": "Банки",
            "telecom": "Телекоммуникации",
            "retail": "Ритейл",
            "energy": "Энергетика",
            "transport": "Транспорт",
            "realestate": "Недвижимость",
            "it": "IT и технологии",
            "chemistry": "Химия",
            "consumer": "Потребительские товары",
            "machinery": "Машиностроение",
            "agriculture": "Сельское хозяйство"
        }
        return sector_names.get(sector_key, sector_key.title())
    
    def _classify_news_type(self, text: str, companies: List[Dict]) -> Dict[str, Any]:
        """Классификация новости по типу"""
        
        text_lower = text.lower()
        classification = {
            "type": "one_company",
            "subtype": None,
            "market_impact": False,
            "regulatory": False
        }
        
        # Проверяем на рыночные новости
        market_keywords = [
            "индекс", "index", "рынок", "market", "биржа", "exchange",
            "торги", "trading", "инвестор", "investor", "капитализация",
            "капитализация", "capitalization", "объем торгов", "trading volume"
        ]
        
        if any(keyword in text_lower for keyword in market_keywords):
            classification["type"] = "market"
            classification["market_impact"] = True
        
        # Проверяем на регуляторные новости
        regulatory_keywords = [
            "цб", "центральный банк", "регулятор", "регулирование",
            "санкции", "санкции", "закон", "законопроект", "постановление",
            "министерство", "правительство", "государство"
        ]
        
        if any(keyword in text_lower for keyword in regulatory_keywords):
            classification["regulatory"] = True
        
        # Определяем подтип
        if "прибыль" in text_lower or "убыток" in text_lower or "выручка" in text_lower:
            classification["subtype"] = "earnings"
        elif "поглощение" in text_lower or "слияние" in text_lower or "m&a" in text_lower:
            classification["subtype"] = "m&a"
        elif "дивиденды" in text_lower or "дивиденд" in text_lower:
            classification["subtype"] = "dividends"
        elif "руководство" in text_lower or "директор" in text_lower or "генеральный директор" in text_lower:
            classification["subtype"] = "management_change"
        elif "технологии" in text_lower or "инновации" in text_lower or "цифровизация" in text_lower:
            classification["subtype"] = "technology"
        
        return classification
    
    async def _create_market_event(self, news: News, classification: Dict[str, Any]) -> Optional[str]:
        """Создать событие для рыночной новости"""
        
        if not self.topic_classifier.graph:
            return None
        
        try:
            # Создаем ID события на основе даты и типа
            from datetime import datetime
            event_date = news.published_at.strftime("%Y-%m-%d")
            event_id = f"market_event:{event_date}:{classification.get('subtype', 'general')}"
            
            # Определяем временные границы события (день новости)
            from_date = news.published_at.strftime("%Y-%m-%dT00:00:00")
            to_date = news.published_at.strftime("%Y-%m-%dT23:59:59")
            
            # Создаем событие
            await self.topic_classifier.graph.create_event_node(
                event_id=event_id,
                event_title=f"Рыночное событие {event_date}",
                from_date=from_date,
                to_date=to_date,
                event_type=classification.get("subtype", "market_general")
            )
            
            # Связываем новость с событием
            await self.topic_classifier.graph.link_news_to_event(str(news.id), event_id)
            
            return event_id
            
        except Exception as e:
            logger.error(f"Failed to create market event: {e}")
            return None
    
    async def _calculate_impact_async(self, news_id: str, company_ids: List[str], published_at: datetime):
        """Асинхронный расчет влияния новости на компании"""
        
        try:
            logger.info(f"Starting impact calculation for news {news_id} on {len(company_ids)} companies")
            
            impacts = await self.impact_calculator.process_news_impact(
                news_id=news_id,
                company_ids=company_ids,
                published_at=published_at
            )
            
            logger.info(f"Impact calculation completed for news {news_id}: {len(impacts)} impacts calculated")
            
        except Exception as e:
            logger.error(f"Impact calculation failed for news {news_id}: {e}")
    
    async def _update_correlations_async(self, company_ids: List[str]):
        """Асинхронное обновление корреляций между компаниями"""
        
        try:
            logger.info(f"Starting correlation update for {len(company_ids)} companies")
            
            # Обновляем корреляции для каждой компании
            for company_id in company_ids:
                try:
                    correlations = await self.covariance_service.calculate_correlations_for_company(
                        company_id=company_id,
                        window="1Y",
                        min_correlation=0.3,
                        max_companies=10
                    )
                    
                    logger.debug(f"Updated {len(correlations)} correlations for {company_id}")
                    
                except Exception as e:
                    logger.debug(f"Failed to update correlations for {company_id}: {e}")
                    continue
            
            logger.info(f"Correlation update completed for {len(company_ids)} companies")
            
        except Exception as e:
            logger.error(f"Correlation update failed: {e}")
    
    async def _write_to_graph(self, news: News, enrichment: Dict[str, Any]):
        """Записываем данные в графовую базу данных"""
        
        if not self.topic_classifier.graph:
            logger.warning("Graph service not initialized, skipping graph write")
            return
        
        try:
            # Создаем новость в графе
            await self.topic_classifier.graph.create_news_node(news)
            
            # Связываем новость с рынком, если это рыночная новость
            news_classification = enrichment.get("news_classification", {})
            if news_classification.get("type") == "market":
                market_id = "moex_market"
                await self.topic_classifier.graph.link_news_to_market(str(news.id), market_id)
            
            # Создаем сущности и связываем с новостью
            entity_ids = []
            for entity_data in enrichment.get("entities", []):
                entity_id = str(uuid4())
                await self.topic_classifier.graph.create_entity_node(
                    entity_id=entity_id,
                    text=entity_data["text"],
                    entity_type=entity_data["type"],
                    confidence=entity_data["confidence"]
                )
                await self.topic_classifier.graph.link_news_to_entity(str(news.id), entity_id)
                entity_ids.append(entity_id)
            
            # Создаем компании и связываем с новостью
            company_ids = []
            for company_data in enrichment.get("companies", []):
                # Используем уникальный ID на основе тикера для избежания дубликатов
                company_id = f"moex:{company_data['secid']}"
                await self.topic_classifier.graph.create_company_node(
                    company_id=company_id,
                    name=company_data["name"],
                    ticker=company_data["secid"],
                    is_traded=company_data["is_traded"]
                )
                await self.topic_classifier.graph.link_news_to_company(str(news.id), company_id)
                
                # Создаем связь с рынком MOEX
                market_id = "moex_market"
                await self.topic_classifier.graph.create_market_node(
                    market_id=market_id,
                    market_name="Московская биржа",
                    country_code="RU",
                    source="MOEX"
                )
                await self.topic_classifier.graph.link_company_to_market(company_id, market_id)
                
                # Создаем связь со страной
                await self.topic_classifier.graph.create_country_node(
                    country_code="RU",
                    country_name="Россия"
                )
                await self.topic_classifier.graph.link_company_to_country(company_id, "RU")
                
                # Создаем финансовый инструмент для компании
                instrument_id = f"moex:{company_data['secid']}:equity"
                await self.topic_classifier.graph.create_instrument_node(
                    instrument_id=instrument_id,
                    symbol=company_data["secid"],
                    instrument_type="equity",
                    exchange="MOEX",
                    currency="RUB"
                )
                await self.topic_classifier.graph.link_company_to_instrument(company_id, instrument_id)
                
                # Создаем связь с сектором, если определен
                sector = self._get_sector_for_ticker(company_data["secid"])
                if sector:
                    sector_id = f"sector:{sector}"
                    sector_name = self._get_sector_name(sector)
                    await self.topic_classifier.graph.create_sector_node(
                        sector_id=sector_id,
                        sector_name=sector_name,
                        taxonomy="ICB"
                    )
                    await self.topic_classifier.graph.link_company_to_sector(company_id, sector_id)
                    
                    # Создаем регулятор для сектора (например, ЦБ РФ для банков)
                    if sector == "banks":
                        regulator_id = "cbr_rf"
                        await self.topic_classifier.graph.create_regulator_node(
                            regulator_id=regulator_id,
                            regulator_name="Центральный банк Российской Федерации",
                            country_code="RU"
                        )
                        await self.topic_classifier.graph.link_regulator_covers_sector(regulator_id, sector_id)
                        await self.topic_classifier.graph.link_regulator_covers_market(regulator_id, market_id)
                
                company_ids.append(company_id)
            
            # Создаем темы и связываем с новостью
            topic_ids = []
            for topic_data in enrichment.get("topics", []):
                # Используем детерминированный ID на основе названия темы для избежания дубликатов
                topic_id = f"topic:{topic_data['topic'].lower().replace(' ', '_')}"
                await self.topic_classifier.graph.create_topic_node(
                    topic_id=topic_id,
                    topic_name=topic_data["topic"],
                    confidence=topic_data["confidence"]
                )
                await self.topic_classifier.graph.link_news_to_topic(str(news.id), topic_id)
                topic_ids.append(topic_id)
            
            logger.info(f"Successfully wrote to graph for news {news.id}: {len(entity_ids)} entities, {len(company_ids)} companies, {len(topic_ids)} topics")
            
        except Exception as e:
            logger.error(f"Error writing to graph: {e}")
            raise
    
    async def close(self):
        """Закрытие ресурсов"""
        if self._initialized:
            if self.moex_linker:
                await self.moex_linker.close()
            if self.impact_calculator:
                await self.impact_calculator.close()
            if self.covariance_service:
                await self.covariance_service.close()
            if self.ceg_service:
                await self.ceg_service.close()
            self._initialized = False
