"""
SRT翻訳システム - モジュールパッケージ

設定管理とエラーハンドリング機能を提供します。
"""

from .config_handler import TranslationConfig, ConfigHandler
from .error_handler import (
    SRTTranslationError,
    SRTParseError, 
    TranslationError,
    APIConnectionError,
    FileError,
    ErrorHandler
)

__all__ = [
    'TranslationConfig',
    'ConfigHandler',
    'SRTTranslationError',
    'SRTParseError',
    'TranslationError', 
    'APIConnectionError',
    'FileError',
    'ErrorHandler'
]

__version__ = "1.0.0"