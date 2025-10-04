# src/services/html_parser/__init__.py
"""
HTML парсеры для различных новостных источников
"""

from .base_html_parser import BaseHTMLParser
from .forbes_parser import ForbesParser
from .interfax_parser import InterfaxParser
from .edisclosure_parser import EDisclosureParser
from .moex_parser import MOEXParser
from .edisclosure_messages_parser import EDisclosureMessagesParser
from .html_parser_service import HTMLParserService

__all__ = [
    'BaseHTMLParser',
    'ForbesParser', 
    'InterfaxParser',
    'EDisclosureParser',
    'MOEXParser',
    'EDisclosureMessagesParser',
    'HTMLParserService'
]
