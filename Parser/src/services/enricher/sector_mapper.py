# src/services/enricher/sector_mapper.py
"""
Маппинг компаний по отраслям (ICB/GICS/NACE)
Интеграция с графовой моделью
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class SectorTaxonomy(str, Enum):
    """Таксономии отраслей"""
    ICB = "ICB"  # Industry Classification Benchmark
    GICS = "GICS"  # Global Industry Classification Standard
    NACE = "NACE"  # European Classification


@dataclass
class SectorInfo:
    """Информация о секторе"""
    id: str
    name: str
    level: int  # 1-4 (от общего к специфичному)
    parent_id: Optional[str] = None
    description: Optional[str] = None


class SectorMapper:
    """
    Маппер для классификации компаний по отраслям
    Поддерживает несколько таксономий
    """
    
    def __init__(self, taxonomy: SectorTaxonomy = SectorTaxonomy.ICB):
        self.taxonomy = taxonomy
        self._sector_hierarchy = self._build_sector_hierarchy()
    
    def _build_sector_hierarchy(self) -> Dict[str, SectorInfo]:
        """Построить иерархию секторов"""
        
        if self.taxonomy == SectorTaxonomy.ICB:
            return self._build_icb_hierarchy()
        elif self.taxonomy == SectorTaxonomy.GICS:
            return self._build_gics_hierarchy()
        elif self.taxonomy == SectorTaxonomy.NACE:
            return self._build_nace_hierarchy()
        else:
            return {}
    
    def _build_icb_hierarchy(self) -> Dict[str, SectorInfo]:
        """Построить ICB иерархию"""
        
        return {
            # Level 1 - Industries
            "1000": SectorInfo("1000", "Oil & Gas", 1, None, "Energy sector"),
            "2000": SectorInfo("2000", "Basic Materials", 1, None, "Materials and chemicals"),
            "3000": SectorInfo("3000", "Industrials", 1, None, "Industrial goods and services"),
            "4000": SectorInfo("4000", "Consumer Goods", 1, None, "Consumer products"),
            "5000": SectorInfo("5000", "Health Care", 1, None, "Healthcare and pharmaceuticals"),
            "6000": SectorInfo("6000", "Consumer Services", 1, None, "Consumer services"),
            "7000": SectorInfo("7000", "Telecommunications", 1, None, "Telecom and media"),
            "8000": SectorInfo("8000", "Utilities", 1, None, "Utilities and infrastructure"),
            "9000": SectorInfo("9000", "Financials", 1, None, "Financial services"),
            "9500": SectorInfo("9500", "Technology", 1, None, "Technology and software"),
            
            # Level 2 - Supersectors (Oil & Gas)
            "1010": SectorInfo("1010", "Oil & Gas Producers", 2, "1000", "Oil and gas extraction"),
            "1020": SectorInfo("1020", "Oil Equipment & Services", 2, "1000", "Oil services and equipment"),
            
            # Level 2 - Supersectors (Basic Materials)
            "2010": SectorInfo("2010", "Chemicals", 2, "2000", "Chemical companies"),
            "2020": SectorInfo("2020", "Forestry & Paper", 2, "2000", "Forestry and paper products"),
            "2030": SectorInfo("2030", "Industrial Metals", 2, "2000", "Metal mining and processing"),
            "2040": SectorInfo("2040", "Mining", 2, "2000", "Mining companies"),
            
            # Level 2 - Supersectors (Industrials)
            "3010": SectorInfo("3010", "Aerospace & Defense", 2, "3000", "Aerospace and defense"),
            "3020": SectorInfo("3020", "General Industrials", 2, "3000", "General industrial companies"),
            "3030": SectorInfo("3030", "Electronic & Electrical Equipment", 2, "3000", "Electronics and electrical"),
            "3040": SectorInfo("3040", "Industrial Engineering", 2, "3000", "Industrial engineering"),
            "3050": SectorInfo("3050", "Industrial Transportation", 2, "3000", "Transportation and logistics"),
            
            # Level 2 - Supersectors (Consumer Goods)
            "4010": SectorInfo("4010", "Automobiles & Parts", 2, "4000", "Automotive industry"),
            "4020": SectorInfo("4020", "Beverages", 2, "4000", "Beverage companies"),
            "4030": SectorInfo("4030", "Food & Drug Retailers", 2, "4000", "Food and drug retail"),
            "4040": SectorInfo("4040", "Food Producers", 2, "4000", "Food production"),
            "4050": SectorInfo("4050", "Household Goods", 2, "4000", "Household products"),
            "4060": SectorInfo("4060", "Personal Care", 2, "4000", "Personal care products"),
            "4070": SectorInfo("4070", "Tobacco", 2, "4000", "Tobacco industry"),
            
            # Level 2 - Supersectors (Health Care)
            "5010": SectorInfo("5010", "Health Care Equipment & Services", 2, "5000", "Medical equipment and services"),
            "5020": SectorInfo("5020", "Pharmaceuticals & Biotechnology", 2, "5000", "Pharma and biotech"),
            
            # Level 2 - Supersectors (Consumer Services)
            "6010": SectorInfo("6010", "General Retailers", 2, "6000", "General retail"),
            "6020": SectorInfo("6020", "Leisure & Hotels", 2, "6000", "Leisure and hospitality"),
            "6030": SectorInfo("6030", "Media", 2, "6000", "Media and entertainment"),
            "6040": SectorInfo("6040", "Support Services", 2, "6000", "Support services"),
            "6050": SectorInfo("6050", "Travel & Tourism", 2, "6000", "Travel and tourism"),
            
            # Level 2 - Supersectors (Telecommunications)
            "7010": SectorInfo("7010", "Fixed Line Telecommunications", 2, "7000", "Fixed line telecom"),
            "7020": SectorInfo("7020", "Mobile Telecommunications", 2, "7000", "Mobile telecom"),
            "7030": SectorInfo("7030", "Telecommunications Equipment", 2, "7000", "Telecom equipment"),
            
            # Level 2 - Supersectors (Utilities)
            "8010": SectorInfo("8010", "Electricity", 2, "8000", "Electric utilities"),
            "8020": SectorInfo("8020", "Gas, Water & Multi-utilities", 2, "8000", "Gas and water utilities"),
            
            # Level 2 - Supersectors (Financials)
            "9010": SectorInfo("9010", "Banks", 2, "9000", "Banking"),
            "9020": SectorInfo("9020", "Non-life Insurance", 2, "9000", "Non-life insurance"),
            "9030": SectorInfo("9030", "Life Insurance", 2, "9000", "Life insurance"),
            "9040": SectorInfo("9040", "Real Estate", 2, "9000", "Real estate"),
            "9050": SectorInfo("9050", "Financial Services", 2, "9000", "Financial services"),
            
            # Level 2 - Supersectors (Technology)
            "9510": SectorInfo("9510", "Software & Computer Services", 2, "9500", "Software and IT services"),
            "9520": SectorInfo("9520", "Technology Hardware & Equipment", 2, "9500", "Technology hardware"),
        }
    
    def _build_gics_hierarchy(self) -> Dict[str, SectorInfo]:
        """Построить GICS иерархию"""
        
        return {
            # Level 1 - Sectors
            "10": SectorInfo("10", "Energy", 1, None, "Energy sector"),
            "15": SectorInfo("15", "Materials", 1, None, "Materials sector"),
            "20": SectorInfo("20", "Industrials", 1, None, "Industrials sector"),
            "25": SectorInfo("25", "Consumer Discretionary", 1, None, "Consumer discretionary"),
            "30": SectorInfo("30", "Consumer Staples", 1, None, "Consumer staples"),
            "35": SectorInfo("35", "Health Care", 1, None, "Health care sector"),
            "40": SectorInfo("40", "Financials", 1, None, "Financials sector"),
            "45": SectorInfo("45", "Information Technology", 1, None, "Information technology"),
            "50": SectorInfo("50", "Communication Services", 1, None, "Communication services"),
            "55": SectorInfo("55", "Utilities", 1, None, "Utilities sector"),
            "60": SectorInfo("60", "Real Estate", 1, None, "Real estate sector"),
        }
    
    def _build_nace_hierarchy(self) -> Dict[str, SectorInfo]:
        """Построить NACE иерархию"""
        
        return {
            # Level 1 - Sections
            "A": SectorInfo("A", "Agriculture, Forestry and Fishing", 1, None, "Primary sector"),
            "B": SectorInfo("B", "Mining and Quarrying", 1, None, "Extractive industries"),
            "C": SectorInfo("C", "Manufacturing", 1, None, "Manufacturing"),
            "D": SectorInfo("D", "Electricity, Gas, Steam and Air Conditioning Supply", 1, None, "Utilities"),
            "E": SectorInfo("E", "Water Supply; Sewerage, Waste Management and Remediation Activities", 1, None, "Water and waste"),
            "F": SectorInfo("F", "Construction", 1, None, "Construction"),
            "G": SectorInfo("G", "Wholesale and Retail Trade; Repair of Motor Vehicles and Motorcycles", 1, None, "Trade"),
            "H": SectorInfo("H", "Transportation and Storage", 1, None, "Transportation"),
            "I": SectorInfo("I", "Accommodation and Food Service Activities", 1, None, "Hospitality"),
            "J": SectorInfo("J", "Information and Communication", 1, None, "Information and communication"),
            "K": SectorInfo("K", "Financial and Insurance Activities", 1, None, "Financial services"),
            "L": SectorInfo("L", "Real Estate Activities", 1, None, "Real estate"),
            "M": SectorInfo("M", "Professional, Scientific and Technical Activities", 1, None, "Professional services"),
            "N": SectorInfo("N", "Administrative and Support Service Activities", 1, None, "Administrative services"),
            "O": SectorInfo("O", "Public Administration and Defence; Compulsory Social Security", 1, None, "Public administration"),
            "P": SectorInfo("P", "Education", 1, None, "Education"),
            "Q": SectorInfo("Q", "Human Health and Social Work Activities", 1, None, "Health and social work"),
            "R": SectorInfo("R", "Arts, Entertainment and Recreation", 1, None, "Arts and entertainment"),
            "S": SectorInfo("S", "Other Service Activities", 1, None, "Other services"),
            "T": SectorInfo("T", "Activities of Households as Employers", 1, None, "Household activities"),
            "U": SectorInfo("U", "Activities of Extraterritorial Organizations and Bodies", 1, None, "International organizations"),
        }
    
    def get_sector_by_ticker(self, ticker: str) -> Optional[SectorInfo]:
        """Получить сектор по тикеру MOEX"""
        
        # Маппинг тикеров MOEX на ICB секторы
        ticker_to_sector = {
            # Oil & Gas
            "GAZP": "1010", "ROSN": "1010", "LKOH": "1010", "NVTK": "1010", 
            "SNGS": "1010", "TATN": "1010", "SIBN": "1010",
            
            # Basic Materials - Mining
            "GMKN": "2040", "NLMK": "2030", "CHMF": "2030", "MAGN": "2030",
            "PLZL": "2040", "ALRS": "2040", "RUAL": "2040", "POGR": "2040",
            
            # Basic Materials - Chemicals
            "PHOR": "2010", "KAZT": "2010", "NKNC": "2010", "AKRN": "2010",
            
            # Financials - Banks
            "SBER": "9010", "VTBR": "9010", "CBOM": "9010", "BSPB": "9010",
            "QIWI": "9050", "TCSG": "9050",
            
            # Consumer Services - Retail
            "MGNT": "6010", "FIVE": "6010", "DSKY": "6010", "LENT": "6010",
            "OZON": "6010", "MVID": "6010",
            
            # Telecommunications
            "MTSS": "7020", "MFON": "7020", "RTKM": "7010",
            
            # Technology
            "YNDX": "9510", "VKCO": "9510", "POSI": "9510", "HHRU": "9510",
            "CIAN": "9510", "TCSG": "9510",
            
            # Consumer Goods - Food
            "ABRD": "4040", "AQUA": "4040", "BELU": "4040", "GCHE": "4040",
            
            # Industrials
            "AFLT": "3050", "NMTP": "3050", "FESH": "3050", "GLTR": "3050",
            
            # Real Estate
            "PIKK": "9040", "LSRG": "9040", "SMLT": "9040", "ETLN": "9040",
            
            # Utilities
            "HYDR": "8010", "IRAO": "8010", "FEES": "8010", "UPRO": "8010",
            "TGKA": "8010", "TGKB": "8010", "OGKB": "8010",
            
            # Health Care
            "MDMG": "5010",
        }
        
        sector_id = ticker_to_sector.get(ticker)
        if sector_id:
            return self._sector_hierarchy.get(sector_id)
        
        return None
    
    def get_sector_by_keywords(self, keywords: List[str]) -> Optional[SectorInfo]:
        """Определить сектор по ключевым словам"""
        
        keyword_to_sector = {
            # Oil & Gas keywords
            "нефть": "1010", "газ": "1010", "нефтегаз": "1010", "энергия": "1010",
            "oil": "1010", "gas": "1010", "energy": "1010", "petroleum": "1010",
            
            # Banking keywords
            "банк": "9010", "кредит": "9010", "финансы": "9010", "банковский": "9010",
            "bank": "9010", "credit": "9010", "finance": "9010", "lending": "9010",
            
            # Technology keywords
            "технологии": "9510", "софт": "9510", "интернет": "9510", "цифровой": "9510",
            "technology": "9510", "software": "9510", "internet": "9510", "digital": "9510",
            
            # Retail keywords
            "ритейл": "6010", "торговля": "6010", "магазин": "6010", "продажи": "6010",
            "retail": "6010", "trade": "6010", "store": "6010", "sales": "6010",
            
            # Mining keywords
            "металлы": "2030", "металлургия": "2030", "добыча": "2040", "шахта": "2040",
            "metals": "2030", "mining": "2040", "steel": "2030", "iron": "2030",
            
            # Telecom keywords
            "связь": "7020", "телеком": "7020", "мобильный": "7020", "сеть": "7020",
            "telecom": "7020", "mobile": "7020", "network": "7020", "communication": "7020",
            
            # Utilities keywords
            "электроэнергия": "8010", "энергетика": "8010", "электричество": "8010",
            "electricity": "8010", "power": "8010", "utility": "8010",
            
            # Real Estate keywords
            "недвижимость": "9040", "строительство": "9040", "девелопмент": "9040",
            "real estate": "9040", "construction": "9040", "property": "9040",
        }
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for pattern, sector_id in keyword_to_sector.items():
                if pattern in keyword_lower:
                    return self._sector_hierarchy.get(sector_id)
        
        return None
    
    def get_parent_sectors(self, sector_id: str) -> List[SectorInfo]:
        """Получить родительские секторы"""
        
        parents = []
        current = self._sector_hierarchy.get(sector_id)
        
        while current and current.parent_id:
            parent = self._sector_hierarchy.get(current.parent_id)
            if parent:
                parents.append(parent)
                current = parent
            else:
                break
        
        return parents
    
    def get_child_sectors(self, sector_id: str) -> List[SectorInfo]:
        """Получить дочерние секторы"""
        
        children = []
        for sector in self._sector_hierarchy.values():
            if sector.parent_id == sector_id:
                children.append(sector)
        
        return children
    
    def get_sector_hierarchy(self, sector_id: str) -> Dict[str, List[SectorInfo]]:
        """Получить полную иерархию сектора"""
        
        return {
            "parents": self.get_parent_sectors(sector_id),
            "current": [self._sector_hierarchy.get(sector_id)] if self._sector_hierarchy.get(sector_id) else [],
            "children": self.get_child_sectors(sector_id)
        }
    
    def get_all_sectors(self) -> List[SectorInfo]:
        """Получить все секторы"""
        return list(self._sector_hierarchy.values())
    
    def get_sectors_by_level(self, level: int) -> List[SectorInfo]:
        """Получить секторы определенного уровня"""
        return [sector for sector in self._sector_hierarchy.values() if sector.level == level]


# ============================================================================
# Пример использования
# ============================================================================

def example_usage():
    """Пример использования SectorMapper"""
    
    mapper = SectorMapper(SectorTaxonomy.ICB)
    
    # Получить сектор по тикеру
    sber_sector = mapper.get_sector_by_ticker("SBER")
    print(f"SBER сектор: {sber_sector.name} (ID: {sber_sector.id})")
    
    # Получить сектор по ключевым словам
    keywords = ["банк", "кредит", "финансы"]
    bank_sector = mapper.get_sector_by_keywords(keywords)
    print(f"Сектор по ключевым словам: {bank_sector.name}")
    
    # Получить иерархию
    hierarchy = mapper.get_sector_hierarchy("9010")
    print(f"Иерархия банковского сектора:")
    for parent in hierarchy["parents"]:
        print(f"  Родитель: {parent.name}")
    print(f"  Текущий: {hierarchy['current'][0].name}")
    for child in hierarchy["children"]:
        print(f"  Дочерний: {child.name}")
    
    # Все секторы уровня 1
    level1_sectors = mapper.get_sectors_by_level(1)
    print(f"\nСекторы уровня 1:")
    for sector in level1_sectors:
        print(f"  {sector.id}: {sector.name}")


if __name__ == "__main__":
    example_usage()
