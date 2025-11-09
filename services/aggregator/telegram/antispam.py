import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import yaml
from pathlib import Path

from telethon.tl.types import Message, MessageEntityTextUrl, MessageEntityUrl


@dataclass
class AdRule:
    """Single advertising detection rule"""
    name: str
    pattern: Optional[re.Pattern] = None
    keywords: List[str] = field(default_factory=list)
    weight: float = 1.0
    enabled: bool = True
    

@dataclass 
class AdDetectorConfig:
    """Configuration for ad detection"""
    threshold: float = 5.0
    trusted_threshold: float = 8.0  # Higher threshold for trusted sources
    
    # Rule categories
    hashtag_rules: List[AdRule] = field(default_factory=list)
    keyword_rules: List[AdRule] = field(default_factory=list)
    url_rules: List[AdRule] = field(default_factory=list)
    structural_rules: List[AdRule] = field(default_factory=list)
    
    # Whitelists/blacklists
    whitelisted_domains: List[str] = field(default_factory=list)
    blacklisted_channels: List[str] = field(default_factory=list)
    trusted_channels: List[str] = field(default_factory=list)


class AntiSpamFilter:
    def __init__(self, config_path: Optional[Path] = None):
        self.config = self._load_config(config_path)
        self._compile_patterns()
        
    def _load_config(self, config_path: Optional[Path]) -> AdDetectorConfig:
        """Load configuration from YAML file"""
        if config_path and config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
                return self._parse_config(config_dict)
        return self._get_default_config()
    
    def _parse_config(self, config_dict: Dict) -> AdDetectorConfig:
        """Parse configuration dictionary into AdDetectorConfig"""
        config = self._get_default_config()
        
        if not config_dict:
            return config
        
        # Override thresholds if provided
        if 'threshold' in config_dict:
            config.threshold = float(config_dict['threshold'])
        if 'trusted_threshold' in config_dict:
            config.trusted_threshold = float(config_dict['trusted_threshold'])
        
        # Parse custom rules if provided
        if 'rules' in config_dict:
            rules = config_dict['rules']
            
            # Hashtag rules
            if 'hashtag_rules' in rules:
                config.hashtag_rules.extend([
                    AdRule(
                        name=r.get('name', ''),
                        keywords=r.get('keywords', []),
                        weight=r.get('weight', 1.0),
                        enabled=r.get('enabled', True)
                    ) for r in rules['hashtag_rules']
                ])
            
            # Keyword rules
            if 'keyword_rules' in rules:
                config.keyword_rules.extend([
                    AdRule(
                        name=r.get('name', ''),
                        keywords=r.get('keywords', []),
                        weight=r.get('weight', 1.0),
                        enabled=r.get('enabled', True)
                    ) for r in rules['keyword_rules']
                ])
        
        # Parse whitelists/blacklists
        if 'whitelisted_domains' in config_dict:
            config.whitelisted_domains.extend(config_dict['whitelisted_domains'])
        if 'blacklisted_channels' in config_dict:
            config.blacklisted_channels.extend(config_dict['blacklisted_channels'])
        if 'trusted_channels' in config_dict:
            config.trusted_channels.extend(config_dict['trusted_channels'])
        
        return config
    
    def _get_default_config(self) -> AdDetectorConfig:
        """Default anti-spam configuration"""
        config = AdDetectorConfig()
        
        # Hashtag rules
        config.hashtag_rules = [
            AdRule(name="ad_hashtags", keywords=["#реклама", "#ad", "#promo", "#промо", "#спонсор"], weight=3.0),
            AdRule(name="partner_hashtags", keywords=["#партнер", "#partner", "#collab"], weight=2.0),
        ]
        
        # Keyword rules
        config.keyword_rules = [
            AdRule(name="casino_keywords", 
                   keywords=["казино", "ставки", "букмекер", "1xbet", "бонус на депозит"], 
                   weight=5.0),
            AdRule(name="discount_keywords", 
                   keywords=["скидка", "промокод", "распродажа", "акция", "выгодное предложение"], 
                   weight=2.0),
            AdRule(name="urgency_keywords",
                   keywords=["только сегодня", "осталось мест", "успей купить", "последний день"],
                   weight=1.5),
            AdRule(name="crypto_scam",
                   keywords=["криптовалюта заработок", "пассивный доход", "финансовая свобода"],
                   weight=3.0),
        ]
        
        # URL pattern rules
        config.url_rules = [
            AdRule(name="utm_params", pattern=re.compile(r'[?&](utm_|ref=|partner=)'), weight=2.0),
            AdRule(name="shorteners", pattern=re.compile(r'(bit\.ly|tinyurl|clck\.ru|vk\.cc)'), weight=1.5),
            AdRule(name="suspicious_tld", pattern=re.compile(r'\.(tk|ml|ga|cf)'), weight=2.0),
        ]
        
        # Structural rules (applied to message structure)
        config.structural_rules = [
            AdRule(name="many_urls", weight=2.0),  # >3 URLs
            AdRule(name="forwarded_ad", weight=3.0),  # Forwarded from known ad channel
            AdRule(name="poll_or_game", weight=2.0),  # Polls/games often used for engagement
            AdRule(name="short_with_links", weight=1.5),  # <50 chars + URLs
        ]
        
        # Whitelisted domains (official sources)
        config.whitelisted_domains = [
            "gov.ru", "cbr.ru", "moex.com", "e-disclosure.ru", "interfax.ru",
            "rbc.ru", "vedomosti.ru", "kommersant.ru", "tass.ru", "ria.ru"
        ]
        
        return config
    
    def _compile_patterns(self):
        """Pre-compile all regex patterns for efficiency"""
        for rule in self.config.url_rules:
            if rule.pattern and isinstance(rule.pattern, str):
                rule.pattern = re.compile(rule.pattern, re.IGNORECASE)
    
    async def check_message(self, message: Message, source_trust_level: int = 5) -> Tuple[bool, float, List[str]]:
        """
        Check if message is advertising/spam
        
        Returns:
            tuple: (is_ad, score, reasons)
        """
        score = 0.0
        reasons = []
        
        # Skip if from trusted channel with high trust
        if source_trust_level >= 9:
            return False, 0.0, []
        
        text = message.text or message.message or ""
        
        # 1. Check hashtags
        if message.entities:
            hashtags = self._extract_hashtags(message)
            for hashtag in hashtags:
                for rule in self.config.hashtag_rules:
                    if rule.enabled and any(kw.lower() in hashtag.lower() for kw in rule.keywords):
                        score += rule.weight
                        reasons.append(f"hashtag:{rule.name}")
        
        # 2. Check keywords in text
        text_lower = text.lower()
        for rule in self.config.keyword_rules:
            if rule.enabled and any(keyword in text_lower for keyword in rule.keywords):
                score += rule.weight
                reasons.append(f"keyword:{rule.name}")
        
        # 3. Check URLs
        urls = self._extract_urls(message)
        if urls:
            # Check URL patterns
            for url in urls:
                for rule in self.config.url_rules:
                    if rule.enabled and rule.pattern and rule.pattern.search(url):
                        score += rule.weight
                        reasons.append(f"url_pattern:{rule.name}")
                
                # Check if URL is whitelisted
                if any(domain in url for domain in self.config.whitelisted_domains):
                    score -= 2.0  # Reduce score for official sources
            
            # Many URLs rule
            if len(urls) > 3:
                score += self._get_rule_weight("many_urls")
                reasons.append("structural:many_urls")
        
        # 4. Check if forwarded from ad channel
        if message.fwd_from:
            channel_username = getattr(message.fwd_from.from_id, 'username', None)
            if channel_username and channel_username in self.config.blacklisted_channels:
                score += self._get_rule_weight("forwarded_ad")
                reasons.append("structural:forwarded_ad")
        
        # 5. Check message type (polls, games, etc)
        if message.poll or message.game:
            score += self._get_rule_weight("poll_or_game")
            reasons.append("structural:poll_or_game")
        
        # 6. Short message with links
        if len(text) < 50 and len(urls) > 0:
            score += self._get_rule_weight("short_with_links")
            reasons.append("structural:short_with_links")
        
        # Determine threshold based on trust level
        threshold = self.config.trusted_threshold if source_trust_level >= 7 else self.config.threshold
        
        is_ad = score >= threshold
        return is_ad, score, reasons
    
    def _extract_hashtags(self, message: Message) -> List[str]:
        """Extract hashtags from message"""
        hashtags = []
        if not message.entities:
            return hashtags
            
        for entity in message.entities:
            if entity.__class__.__name__ == 'MessageEntityHashtag':
                start = entity.offset
                end = entity.offset + entity.length
                hashtag = message.text[start:end] if message.text else ""
                hashtags.append(hashtag)
        
        return hashtags
    
    def _extract_urls(self, message: Message) -> List[str]:
        """Extract all URLs from message"""
        urls = []
        
        # Extract from entities
        if message.entities:
            for entity in message.entities:
                if isinstance(entity, MessageEntityUrl):
                    start = entity.offset
                    end = entity.offset + entity.length
                    url = message.text[start:end] if message.text else ""
                    urls.append(url)
                elif isinstance(entity, MessageEntityTextUrl):
                    urls.append(entity.url)
        
        # Also extract URLs from message text using regex
        if message.text:
            url_pattern = re.compile(r'https?://[^\s]+')
            urls.extend(url_pattern.findall(message.text))
        
        return list(set(urls))  # Remove duplicates
    
    def _get_rule_weight(self, rule_name: str) -> float:
        """Get weight for a structural rule by name"""
        for rule in self.config.structural_rules:
            if rule.name == rule_name:
                return rule.weight
        return 1.0