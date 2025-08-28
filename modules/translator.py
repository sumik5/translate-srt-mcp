"""LM Studio API連携翻訳モジュール（一括翻訳版）."""

import asyncio
import json
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from pydantic import BaseModel

from .srt_parser import Subtitle

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Translation specific error."""
    pass


class LMStudioAPIError(Exception):
    """LM Studio API specific error."""
    pass


class TranslationRequest(BaseModel):
    """LM Studio API翻訳リクエスト."""
    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.3
    max_tokens: Optional[int] = None


class Translator:
    """LM Studio APIと連携して字幕翻訳を行うクラス."""
    
    def __init__(
        self, 
        lm_studio_url: str,
        model_name: str,
        request_timeout: float = 300.0
    ):
        """
        翻訳クラスを初期化.
        
        Args:
            lm_studio_url: LM Studio API のベースURL
            model_name: 使用するモデル名
            request_timeout: リクエストタイムアウト（秒）- デフォルト5分
        """
        self.base_url = lm_studio_url.rstrip('/')
        # /v1が含まれていない場合は追加
        if '/v1' not in self.base_url:
            self.base_url = self.base_url + '/v1'
        
        self.model = model_name
        self.timeout = httpx.Timeout(request_timeout)
        self.client = None
        
    async def __aenter__(self):
        """非同期コンテキストマネージャーのエントリー."""
        self.client = httpx.AsyncClient(timeout=self.timeout)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーのエグジット."""
        if self.client:
            await self.client.aclose()
    
    async def translate_subtitles(self, subtitles: List[Subtitle]) -> List[Subtitle]:
        """
        字幕リストを一括で翻訳.
        
        Args:
            subtitles: 翻訳対象の字幕リスト
            
        Returns:
            翻訳された字幕リスト
        """
        if not subtitles:
            return []
        
        # 一時的なクライアント作成（コンテキストマネージャー外での使用用）
        if self.client is None:
            self.client = httpx.AsyncClient(timeout=self.timeout)
            close_client = True
        else:
            close_client = False
        
        try:
            # SRT形式の文字列を作成
            srt_text = self._create_srt_text(subtitles)
            
            # プロンプトを構築
            prompt = self._build_bulk_translation_prompt(srt_text)
            
            # 翻訳実行
            logger.info(f"Translating {len(subtitles)} subtitles in bulk...")
            translated_srt = await self._make_api_request(prompt)
            
            # 翻訳結果をパース
            translated_subtitles = self._parse_translated_srt(translated_srt, subtitles)
            
            logger.info(f"Successfully translated {len(translated_subtitles)} subtitles")
            return translated_subtitles
            
        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            raise TranslationError(f"Failed to translate subtitles: {str(e)}") from e
        finally:
            if close_client and self.client:
                await self.client.aclose()
                self.client = None
    
    def _create_srt_text(self, subtitles: List[Subtitle]) -> str:
        """字幕リストからSRT形式のテキストを作成."""
        srt_lines = []
        for subtitle in subtitles:
            srt_lines.append(str(subtitle.index))
            srt_lines.append(f"{subtitle.start_time} --> {subtitle.end_time}")
            srt_lines.append(subtitle.text)
            srt_lines.append("")  # 空行
        
        return "\n".join(srt_lines)
    
    def _build_bulk_translation_prompt(self, srt_text: str) -> str:
        """一括翻訳用のプロンプトを構築."""
        return srt_text
    
    def _parse_translated_srt(self, translated_text: str, original_subtitles: List[Subtitle]) -> List[Subtitle]:
        """
        翻訳されたSRTテキストをパースして字幕オブジェクトのリストに変換.
        
        Args:
            translated_text: 翻訳されたSRTテキスト
            original_subtitles: 元の字幕リスト（タイミング情報を保持）
            
        Returns:
            翻訳された字幕のリスト
        """
        # 字幕ブロックを分割
        blocks = re.split(r'\n\s*\n', translated_text.strip())
        translated_subtitles = []
        
        for i, block in enumerate(blocks):
            if not block.strip():
                continue
                
            lines = block.strip().split('\n')
            if len(lines) < 3:
                logger.warning(f"Invalid subtitle block at index {i}: {block}")
                continue
            
            try:
                # 番号をスキップ（1行目）
                # タイムコードをスキップ（2行目）
                # 3行目以降がテキスト
                translated_text_lines = lines[2:]
                translated_text = '\n'.join(translated_text_lines)
                
                # 元の字幕のタイミング情報を使用
                if i < len(original_subtitles):
                    original = original_subtitles[i]
                    translated_subtitle = Subtitle(
                        index=original.index,
                        start_time=original.start_time,
                        end_time=original.end_time,
                        text=translated_text
                    )
                    translated_subtitles.append(translated_subtitle)
                else:
                    logger.warning(f"No corresponding original subtitle for index {i}")
                    
            except Exception as e:
                logger.error(f"Failed to parse subtitle block at index {i}: {e}")
                # エラーの場合は元のテキストを使用
                if i < len(original_subtitles):
                    translated_subtitles.append(original_subtitles[i])
        
        # 翻訳されなかった字幕がある場合は元のテキストを使用
        if len(translated_subtitles) < len(original_subtitles):
            logger.warning(f"Some subtitles were not translated. Using original text for remaining {len(original_subtitles) - len(translated_subtitles)} subtitles")
            translated_subtitles.extend(original_subtitles[len(translated_subtitles):])
        
        return translated_subtitles
    
    async def _make_api_request(self, prompt: str) -> str:
        """
        LM Studio APIにリクエストを送信.
        
        Args:
            prompt: 翻訳プロンプト
            
        Returns:
            翻訳結果
            
        Raises:
            LMStudioAPIError: API呼び出しが失敗した場合
        """
        try:
            request_data = TranslationRequest(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "あなたは映像字幕の翻訳専門家です。SRT形式を正確に維持しながら、自然で読みやすい日本語字幕を作成してください。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3
            )
            
            # URLが既に/v1を含む場合は、/chat/completionsのみ追加
            if self.base_url.endswith('/v1'):
                api_url = f"{self.base_url}/chat/completions"
            else:
                api_url = urljoin(self.base_url, "chat/completions")
            
            response = await self.client.post(
                api_url,
                json=request_data.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                error_msg = result.get("error", {}).get("message", str(result["error"]))
                raise LMStudioAPIError(f"API Error: {error_msg}")
            
            if "choices" not in result or not result["choices"]:
                raise LMStudioAPIError("APIレスポンスにchoicesが含まれていません")
            
            translated_text = result["choices"][0]["message"]["content"].strip()
            
            if not translated_text:
                raise LMStudioAPIError("翻訳結果が空です")
                
            return translated_text
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
            logger.error(f"API request failed: {error_msg}")
            raise LMStudioAPIError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"Request Error: {str(e)}"
            logger.error(f"API request failed: {error_msg}")
            raise LMStudioAPIError(error_msg) from e
        except (KeyError, json.JSONDecodeError) as e:
            error_msg = f"Response parsing error: {str(e)}"
            logger.error(f"Failed to parse API response: {error_msg}")
            raise LMStudioAPIError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Unexpected error during API request: {error_msg}")
            raise LMStudioAPIError(error_msg) from e