"""
設定管理モジュール

SRT翻訳システムの設定値を管理し、検証を行います。
"""

import os
import re
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass
class TranslationConfig:
    """翻訳設定を格納するデータクラス"""
    lm_studio_url: str
    model_name: str
    timeout: int = 30
    max_retries: int = 3
    
    def __post_init__(self):
        """初期化後の検証"""
        if self.timeout <= 0:
            raise ValueError("タイムアウト値は正の整数である必要があります")
        if self.max_retries < 0:
            raise ValueError("リトライ回数は0以上である必要があります")


class ConfigHandler:
    """設定管理クラス"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    def validate_config(self, config: TranslationConfig) -> bool:
        """
        設定値の検証
        
        Args:
            config: 検証対象の設定
            
        Returns:
            bool: 検証結果（True: 成功, False: 失敗）
        """
        try:
            # URL検証
            if not self.validate_url(config.lm_studio_url):
                self.logger.error(f"無効なLM Studio URL: {config.lm_studio_url}")
                return False
            
            # モデル名検証
            if not self.validate_model_name(config.model_name):
                self.logger.error(f"無効なモデル名: {config.model_name}")
                return False
            
            # 数値範囲検証
            if config.timeout <= 0:
                self.logger.error(f"タイムアウト値が無効: {config.timeout}")
                return False
                
            if config.max_retries < 0:
                self.logger.error(f"リトライ回数が無効: {config.max_retries}")
                return False
            
            self.logger.info("設定検証が完了しました")
            return True
            
        except Exception as e:
            self.logger.error(f"設定検証中にエラーが発生: {str(e)}")
            return False
    
    def validate_url(self, url: str) -> bool:
        """
        URL形式の検証
        
        Args:
            url: 検証対象のURL
            
        Returns:
            bool: 検証結果
        """
        try:
            if not url or not isinstance(url, str):
                return False
            
            # 基本的なURL形式チェック
            parsed = urlparse(url.strip())
            
            # スキームチェック（http/https）
            if parsed.scheme not in ('http', 'https'):
                return False
            
            # ホスト名チェック
            if not parsed.netloc:
                return False
            
            # ポート番号チェック（指定されている場合）
            if parsed.port is not None:
                if not (1 <= parsed.port <= 65535):
                    return False
            
            return True
            
        except Exception:
            return False
    
    def validate_model_name(self, model_name: str) -> bool:
        """
        モデル名の検証
        
        Args:
            model_name: 検証対象のモデル名
            
        Returns:
            bool: 検証結果
        """
        if not model_name or not isinstance(model_name, str):
            return False
        
        # 空白文字のみでないかチェック
        if not model_name.strip():
            return False
        
        # 基本的な文字列パターンチェック
        # アルファベット、数字、ハイフン、アンダースコア、ピリオド、スラッシュを許可
        pattern = r'^[a-zA-Z0-9._/-]+$'
        if not re.match(pattern, model_name.strip()):
            return False
        
        return True
    
    
    def load_from_env(self) -> Optional[TranslationConfig]:
        """
        環境変数から設定を読み込み
        
        Returns:
            TranslationConfig: 設定オブジェクト（失敗時はNone）
        """
        try:
            lm_studio_url = os.getenv('LM_STUDIO_URL')
            model_name = os.getenv('MODEL_NAME')
            
            if not lm_studio_url or not model_name:
                self.logger.error("必須環境変数が設定されていません (LM_STUDIO_URL, MODEL_NAME)")
                return None
            
            config = TranslationConfig(
                lm_studio_url=lm_studio_url,
                model_name=model_name,
                timeout=int(os.getenv('TIMEOUT', '30')),
                max_retries=int(os.getenv('MAX_RETRIES', '3'))
            )
            
            if self.validate_config(config):
                return config
            else:
                return None
                
        except ValueError as e:
            self.logger.error(f"環境変数の値が無効: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"環境変数読み込み中にエラー: {str(e)}")
            return None


# 基本テスト機能
def _basic_validation_test():
    """基本的な検証機能のテスト"""
    handler = ConfigHandler()
    
    # URL検証テスト
    assert handler.validate_url("http://localhost:1234") == True
    assert handler.validate_url("https://api.example.com:8080") == True
    assert handler.validate_url("invalid-url") == False
    assert handler.validate_url("") == False
    print("✓ URL検証テスト成功")
    
    # モデル名検証テスト
    assert handler.validate_model_name("llama-3-8b") == True
    assert handler.validate_model_name("models/gpt-4") == True
    assert handler.validate_model_name("") == False
    assert handler.validate_model_name("   ") == False
    print("✓ モデル名検証テスト成功")
    
    # 設定検証テスト
    valid_config = TranslationConfig(
        lm_studio_url="http://localhost:1234",
        model_name="llama-3-8b",
        timeout=30,
        max_retries=3
    )
    assert handler.validate_config(valid_config) == True
    print("✓ 設定検証テスト成功")
    
    print("全ての基本検証テストが成功しました")


if __name__ == "__main__":
    # ログ設定
    logging.basicConfig(level=logging.INFO)
    
    # 基本テスト実行
    _basic_validation_test()