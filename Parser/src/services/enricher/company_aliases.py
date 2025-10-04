# src/services/enricher/company_aliases.py
"""
Централизованный модуль для управления алиасами компаний MOEX
Используется в moex_linker и topic_classifier для избежания дублирования
"""

import logging
import json
from typing import Dict, Optional, List, Set
from pathlib import Path

logger = logging.getLogger(__name__)


class CompanyAliasManager:
    """
    Менеджер алиасов компаний
    Поддерживает ручные алиасы + автоматическое обучение
    """
    
    # Базовые известные алиасы (вручную проверенные)
    KNOWN_ALIASES: Dict[str, str] = {
        # Сбербанк
        "сбер": "SBER", "сбербанк": "SBER", "sberbank": "SBER",
        "сберегательный банк": "SBER", "сбербанк россии": "SBER",
        
        # Газпром
        "газпром": "GAZP", "газ": "GAZP", "gazprom": "GAZP",
        
        # ВТБ
        "втб": "VTBR", "vtb": "VTBR", "втб банк": "VTBR",
        
        # Роснефть
        "роснефть": "ROSN", "rosneft": "ROSN",
        
        # Лукойл
        "лукойл": "LKOH", "lukoil": "LKOH", "лук": "LKOH",
        
        # Яндекс
        "яндекс": "YNDX", "yandex": "YNDX", "яндекс нв": "YNDX",
        
        # МТС
        "мтс": "MTSS", "mts": "MTSS", "мобильные телесистемы": "MTSS",
        
        # Норникель
        "норникель": "GMKN", "норильский никель": "GMKN", "norilsk": "GMKN",
        "гмк": "GMKN", "гмк норильский никель": "GMKN",
        
        # Новатэк
        "новатэк": "NVTK", "novatek": "NVTK",
        
        # Полюс
        "полюс": "PLZL", "полюс золото": "PLZL", "polyus": "PLZL",
        
        # Алроса
        "алроса": "ALRS", "alrosa": "ALRS",
        
        # Магнит
        "магнит": "MGNT", "magnit": "MGNT",
        
        # X5
        "x5": "FIVE", "икс файв": "FIVE", "x5 retail": "FIVE",
        "пятерочка": "FIVE", "перекресток": "FIVE",
        
        # Мегафон
        "мегафон": "MFON", "megafon": "MFON",
        
        # Аэрофлот
        "аэрофлот": "AFLT", "aeroflot": "AFLT",
        
        # РусГидро
        "русгидро": "HYDR", "rushydro": "HYDR",
        
        # Интер РАО
        "интер рао": "IRAO", "inter rao": "IRAO",
        
        # ФСК ЕЭС
        "фск": "FEES", "фск еэс": "FEES", "россети": "FEES",
        
        # Сургутнефтегаз
        "сургут": "SNGS", "сургутнефтегаз": "SNGS", "surgutneftegas": "SNGS",
        
        # Татнефть
        "татнефть": "TATN", "tatneft": "TATN",
        
        # НЛМК
        "нлмк": "NLMK", "новолипецкий": "NLMK", "nlmk": "NLMK",
        
        # ММК
        "ммк": "MAGN", "магнитогорский": "MAGN", "mmk": "MAGN",
        
        # Северсталь
        "северсталь": "CHMF", "severstal": "CHMF",
        
        # Евраз
        "евраз": "EVRAZ", "evraz": "EVRAZ",
        
        # ПИК
        "пик": "PIKK", "pik": "PIKK", "группа пик": "PIKK",
        
        # ЛСР
        "лср": "LSRG", "lsr": "LSRG", "группа лср": "LSRG",
        
        # Детский мир
        "детский мир": "DSKY", "detsky mir": "DSKY",
        
        # Московская биржа
        "мосбиржа": "MOEX", "московская биржа": "MOEX", "moex": "MOEX",
        
        # ТГК-1
        "тгк-1": "TGKA", "тгк1": "TGKA",
        
        # ОГК-2
        "огк-2": "OGKB", "огк2": "OGKB",
        
        # Русал
        "русал": "RUAL", "rusal": "RUAL", "юнайтед компани русал": "RUAL",
        
        # ФосАгро
        "фосагро": "PHOR", "phosagro": "PHOR",
        
        # МКБ
        "мкб": "CBOM", "московский кредитный банк": "CBOM",
        
        # Positive Technologies
        "positive": "POSI", "позитив": "POSI", "positive technologies": "POSI",
        
        # Ozon
        "озон": "OZON", "ozon": "OZON",
        
        # HeadHunter
        "хэдхантер": "HHRU", "headhunter": "HHRU", "hh": "HHRU",
        
        # MD Medical Group
        "мд медикал": "MDMG", "мать и дитя": "MDMG",
        
        # Petropavlovsk
        "петропавловск": "POGR", "petropavlovsk": "POGR",
        
        # En+ Group
        "эн+": "ENPG", "en+": "ENPG", "en plus": "ENPG",
    }
    
    def __init__(self, learned_aliases_file: Optional[str] = None):
        """
        Инициализация менеджера алиасов
        
        Args:
            learned_aliases_file: Путь к файлу с автоматически выученными алиасами
        """
        self.learned_aliases: Dict[str, str] = {}
        self.learned_aliases_file = learned_aliases_file or "data/learned_aliases.json"
        
        # Загружаем выученные алиасы
        self._load_learned_aliases()
    
    def _load_learned_aliases(self):
        """Загрузить автоматически выученные алиасы из файла"""
        try:
            filepath = Path(self.learned_aliases_file)
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.learned_aliases = json.load(f)
                logger.info(f"Loaded {len(self.learned_aliases)} learned aliases from {filepath}")
        except Exception as e:
            logger.warning(f"Could not load learned aliases: {e}")
            self.learned_aliases = {}
    
    def save_learned_aliases(self):
        """Сохранить выученные алиасы в файл"""
        try:
            filepath = Path(self.learned_aliases_file)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.learned_aliases, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved {len(self.learned_aliases)} learned aliases to {filepath}")
        except Exception as e:
            logger.error(f"Could not save learned aliases: {e}")
    
    def get_ticker(self, alias: str) -> Optional[str]:
        """
        Получить тикер по алиасу
        
        Args:
            alias: Алиас компании (нормализованный)
            
        Returns:
            Тикер или None
        """
        alias_lower = alias.lower().strip()
        
        # Сначала проверяем известные алиасы
        if alias_lower in self.KNOWN_ALIASES:
            return self.KNOWN_ALIASES[alias_lower]
        
        # Затем проверяем выученные
        if alias_lower in self.learned_aliases:
            return self.learned_aliases[alias_lower]
        
        return None
    
    def add_learned_alias(self, alias: str, ticker: str, auto_save: bool = True):
        """
        Добавить новый выученный алиас
        
        Args:
            alias: Алиас компании
            ticker: Тикер MOEX
            auto_save: Автоматически сохранить в файл
        """
        alias_lower = alias.lower().strip()
        
        # Не перезаписываем известные алиасы
        if alias_lower in self.KNOWN_ALIASES:
            return
        
        self.learned_aliases[alias_lower] = ticker
        logger.info(f"Learned new alias: {alias_lower} -> {ticker}")
        
        if auto_save:
            self.save_learned_aliases()
    
    def get_all_aliases(self) -> Dict[str, str]:
        """Получить все алиасы (известные + выученные)"""
        return {**self.KNOWN_ALIASES, **self.learned_aliases}
    
    def get_aliases_for_ticker(self, ticker: str) -> List[str]:
        """Получить все алиасы для данного тикера"""
        aliases = []
        all_aliases = self.get_all_aliases()
        
        for alias, tick in all_aliases.items():
            if tick == ticker:
                aliases.append(alias)
        
        return aliases
    
    def clear_learned_aliases(self):
        """Очистить все выученные алиасы"""
        self.learned_aliases = {}
        self.save_learned_aliases()


# Глобальный экземпляр (синглтон)
_global_alias_manager: Optional[CompanyAliasManager] = None


def get_alias_manager() -> CompanyAliasManager:
    """Получить глобальный экземпляр менеджера алиасов"""
    global _global_alias_manager
    
    if _global_alias_manager is None:
        _global_alias_manager = CompanyAliasManager()
    
    return _global_alias_manager

