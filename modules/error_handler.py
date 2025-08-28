"""
エラーハンドリングモジュール

SRT翻訳システムの例外クラスとエラー処理機能を提供します。
"""

import logging
import traceback
import datetime
from typing import Dict, Optional, Any


class SRTTranslationError(Exception):
    """SRT翻訳システムの基底例外クラス"""
    
    def __init__(self, message: str, error_code: str = None, context: Dict[str, Any] = None):
        """
        初期化
        
        Args:
            message: エラーメッセージ
            error_code: エラーコード
            context: エラーコンテキスト情報
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
        self.timestamp = datetime.datetime.now()


class SRTParseError(SRTTranslationError):
    """SRT解析エラー"""
    
    def __init__(self, message: str, line_number: int = None, file_path: str = None):
        """
        SRT解析エラーの初期化
        
        Args:
            message: エラーメッセージ
            line_number: エラーが発生した行番号
            file_path: エラーが発生したファイルパス
        """
        context = {}
        if line_number is not None:
            context['line_number'] = line_number
        if file_path:
            context['file_path'] = file_path
            
        super().__init__(message, "SRT_PARSE_ERROR", context)


class TranslationError(SRTTranslationError):
    """翻訳処理エラー"""
    
    def __init__(self, message: str, model_name: str = None, api_response: str = None):
        """
        翻訳処理エラーの初期化
        
        Args:
            message: エラーメッセージ
            model_name: 使用していたモデル名
            api_response: API応答内容
        """
        context = {}
        if model_name:
            context['model_name'] = model_name
        if api_response:
            context['api_response'] = api_response
            
        super().__init__(message, "TRANSLATION_ERROR", context)


class APIConnectionError(SRTTranslationError):
    """API接続エラー"""
    
    def __init__(self, message: str, url: str = None, status_code: int = None, timeout: float = None):
        """
        API接続エラーの初期化
        
        Args:
            message: エラーメッセージ
            url: 接続先URL
            status_code: HTTPステータスコード
            timeout: タイムアウト時間
        """
        context = {}
        if url:
            context['url'] = url
        if status_code is not None:
            context['status_code'] = status_code
        if timeout is not None:
            context['timeout'] = timeout
            
        super().__init__(message, "API_CONNECTION_ERROR", context)


class FileError(SRTTranslationError):
    """ファイル操作エラー"""
    
    def __init__(self, message: str, file_path: str = None, operation: str = None):
        """
        ファイル操作エラーの初期化
        
        Args:
            message: エラーメッセージ
            file_path: 操作対象ファイルパス
            operation: 実行していた操作
        """
        context = {}
        if file_path:
            context['file_path'] = file_path
        if operation:
            context['operation'] = operation
            
        super().__init__(message, "FILE_ERROR", context)


class ErrorHandler:
    """エラー処理クラス"""
    
    def __init__(self, logger_name: str = __name__):
        """
        初期化
        
        Args:
            logger_name: ロガー名
        """
        self.logger = logging.getLogger(logger_name)
        
    def log_error(self, error: Exception, context: Dict[str, Any] = None) -> None:
        """
        エラーをログに記録
        
        Args:
            error: ログに記録する例外
            context: 追加のコンテキスト情報
        """
        try:
            # エラー情報の収集
            error_info = {
                'error_type': error.__class__.__name__,
                'error_message': str(error),
                'timestamp': datetime.datetime.now().isoformat(),
            }
            
            # SRTTranslationErrorの場合は追加情報を含める
            if isinstance(error, SRTTranslationError):
                error_info.update({
                    'error_code': error.error_code,
                    'error_context': error.context,
                })
            
            # 追加コンテキストがある場合は含める
            if context:
                error_info['additional_context'] = context
            
            # スタックトレースを取得
            stack_trace = traceback.format_exc()
            error_info['stack_trace'] = stack_trace
            
            # ログレベルに応じて記録
            if isinstance(error, (APIConnectionError, FileError)):
                self.logger.error(f"重大なエラー: {error_info}")
            elif isinstance(error, (SRTParseError, TranslationError)):
                self.logger.warning(f"処理エラー: {error_info}")
            else:
                self.logger.error(f"未知のエラー: {error_info}")
                
        except Exception as log_error:
            # ログ記録自体がエラーになった場合の対処
            self.logger.critical(f"ログ記録中にエラーが発生: {str(log_error)}")
            self.logger.critical(f"元のエラー: {str(error)}")
    
    def format_user_message(self, error: Exception) -> str:
        """
        ユーザー向けエラーメッセージ生成
        
        Args:
            error: フォーマット対象の例外
            
        Returns:
            str: ユーザー向けのエラーメッセージ
        """
        try:
            if isinstance(error, SRTParseError):
                base_message = "SRTファイルの解析に失敗しました。"
                if 'line_number' in error.context:
                    base_message += f" (行番号: {error.context['line_number']})"
                if 'file_path' in error.context:
                    base_message += f" (ファイル: {error.context['file_path']})"
                return base_message
                
            elif isinstance(error, TranslationError):
                base_message = "翻訳処理に失敗しました。"
                if 'model_name' in error.context:
                    base_message += f" 使用モデル: {error.context['model_name']}"
                return base_message
                
            elif isinstance(error, APIConnectionError):
                base_message = "APIへの接続に失敗しました。"
                if 'url' in error.context:
                    base_message += f" 接続先: {error.context['url']}"
                if 'status_code' in error.context:
                    base_message += f" (ステータスコード: {error.context['status_code']})"
                return base_message
                
            elif isinstance(error, FileError):
                base_message = "ファイル操作に失敗しました。"
                if 'file_path' in error.context:
                    base_message += f" ファイル: {error.context['file_path']}"
                if 'operation' in error.context:
                    base_message += f" (操作: {error.context['operation']})"
                return base_message
                
            elif isinstance(error, SRTTranslationError):
                return f"処理中にエラーが発生しました: {error.message}"
                
            else:
                return f"予期しないエラーが発生しました: {str(error)}"
                
        except Exception:
            return "エラーメッセージの生成に失敗しました。システム管理者にお問い合わせください。"
    
    def handle_error(self, error: Exception, context: Dict[str, Any] = None) -> str:
        """
        エラーの総合的な処理
        
        Args:
            error: 処理対象の例外
            context: 追加のコンテキスト情報
            
        Returns:
            str: ユーザー向けメッセージ
        """
        # エラーをログに記録
        self.log_error(error, context)
        
        # ユーザー向けメッセージを生成して返す
        return self.format_user_message(error)
    
    @staticmethod
    def create_context(operation: str = None, file_path: str = None, 
                      line_number: int = None, **kwargs) -> Dict[str, Any]:
        """
        コンテキスト情報を作成
        
        Args:
            operation: 実行中の操作
            file_path: 処理中のファイルパス
            line_number: 処理中の行番号
            **kwargs: その他の情報
            
        Returns:
            Dict[str, Any]: コンテキスト辞書
        """
        context = {}
        
        if operation:
            context['operation'] = operation
        if file_path:
            context['file_path'] = file_path
        if line_number is not None:
            context['line_number'] = line_number
            
        # 追加の情報があれば含める
        context.update(kwargs)
        
        return context


# 基本テスト機能
def _basic_error_handling_test():
    """基本的なエラーハンドリング機能のテスト"""
    # ログ設定
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    error_handler = ErrorHandler()
    
    # SRTParseErrorのテスト
    parse_error = SRTParseError("無効なタイムスタンプ形式", line_number=5, file_path="test.srt")
    user_msg = error_handler.format_user_message(parse_error)
    print(f"SRTParseError: {user_msg}")
    assert "行番号: 5" in user_msg
    assert "test.srt" in user_msg
    
    # TranslationErrorのテスト
    translation_error = TranslationError("翻訳APIの応答が異常", model_name="llama-3-8b")
    user_msg = error_handler.format_user_message(translation_error)
    print(f"TranslationError: {user_msg}")
    assert "llama-3-8b" in user_msg
    
    # APIConnectionErrorのテスト
    api_error = APIConnectionError("接続タイムアウト", url="http://localhost:1234", timeout=30.0)
    user_msg = error_handler.format_user_message(api_error)
    print(f"APIConnectionError: {user_msg}")
    assert "localhost:1234" in user_msg
    
    # FileErrorのテスト
    file_error = FileError("ファイルが見つかりません", file_path="input.srt", operation="読み込み")
    user_msg = error_handler.format_user_message(file_error)
    print(f"FileError: {user_msg}")
    assert "input.srt" in user_msg
    assert "読み込み" in user_msg
    
    # コンテキスト作成テスト
    context = ErrorHandler.create_context(
        operation="翻訳",
        file_path="test.srt",
        line_number=10,
        model_name="llama-3-8b"
    )
    assert context['operation'] == "翻訳"
    assert context['model_name'] == "llama-3-8b"
    print("✓ コンテキスト作成テスト成功")
    
    print("全てのエラーハンドリングテストが成功しました")


if __name__ == "__main__":
    # 基本テスト実行
    _basic_error_handling_test()