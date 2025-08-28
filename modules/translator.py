"""LM Studio API連携翻訳モジュール."""

import asyncio
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urljoin

import httpx
from pydantic import ValidationError

from .models import Subtitle, TranslationContext, TranslationRequest

logger = logging.getLogger(__name__)


class TranslationError(Exception):
    """Translation specific error."""
    pass


class LMStudioAPIError(Exception):
    """LM Studio API specific error."""
    pass


class Translator:
    """LM Studio APIと連携して字幕翻訳を行うクラス."""
    
    def __init__(
        self, 
        lm_studio_url: str,
        model_name: str,
        max_concurrent_requests: int = 3,
        request_timeout: float = 30.0,
        rate_limit_delay: float = 1.0
    ):
        """
        翻訳クラスを初期化.
        
        Args:
            lm_studio_url: LM Studio API のベースURL
            model_name: 使用するモデル名
            max_concurrent_requests: 最大同時リクエスト数
            request_timeout: リクエストタイムアウト（秒）
            rate_limit_delay: レート制限のための遅延（秒）
        """
        self.base_url = lm_studio_url.rstrip('/')
        self.model = model_name
        self.max_concurrent_requests = max_concurrent_requests
        self.request_timeout = request_timeout
        self.rate_limit_delay = rate_limit_delay
        self.semaphore = asyncio.Semaphore(max_concurrent_requests)
        
        # HTTPクライアントの設定
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(request_timeout),
            limits=httpx.Limits(max_connections=max_concurrent_requests * 2)
        )
    
    async def __aenter__(self):
        """非同期コンテキストマネージャーの開始."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """非同期コンテキストマネージャーの終了."""
        await self.client.aclose()
    
    def build_prompt(
        self, 
        current_text: str, 
        context: TranslationContext
    ) -> str:
        """
        翻訳用プロンプトを構築.
        
        Args:
            current_text: 翻訳対象のテキスト
            context: 翻訳コンテキスト
            
        Returns:
            構築されたプロンプト文字列
        """
        prompt_parts = [
            "これは映像コンテンツのSRT字幕データです。自然で読みやすい日本語に翻訳してください。",
            "",
            "翻訳時の注意点:",
            "- 字幕として適切な長さに調整してください",
            "- 前後の文脈を考慮して自然な翻訳を心がけてください", 
            "- 映像に合わせた読みやすい表現にしてください",
            "- 翻訳結果のみを返してください（説明や追加情報は不要）",
            ""
        ]
        
        # 前の文脈を追加
        if context.previous_subtitles:
            prompt_parts.extend([
                "前の文脈:",
                "\n".join(f"- {text}" for text in context.previous_subtitles[-3:]),
                ""
            ])
        
        # 翻訳対象を追加
        prompt_parts.extend([
            "翻訳対象:",
            current_text,
            ""
        ])
        
        # 次の文脈を追加
        if context.next_subtitles:
            prompt_parts.extend([
                "次の文脈:",
                "\n".join(f"- {text}" for text in context.next_subtitles[:2]),
                ""
            ])
        
        # シーン情報があれば追加
        if context.scene_description:
            prompt_parts.extend([
                f"シーン情報: {context.scene_description}",
                ""
            ])
        
        # 話者情報があれば追加
        if context.speaker_info:
            prompt_parts.extend([
                f"話者情報: {context.speaker_info}",
                ""
            ])
        
        return "\n".join(prompt_parts)
    
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
                        "content": "あなたは映像字幕の翻訳専門家です。自然で読みやすい日本語字幕を作成してください。"
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            api_url = urljoin(self.base_url, "/v1/chat/completions")
            
            async with self.semaphore:
                response = await self.client.post(
                    api_url,
                    json=request_data.model_dump(),
                    headers={"Content-Type": "application/json"}
                )
                
                # レート制限対応
                if self.rate_limit_delay > 0:
                    await asyncio.sleep(self.rate_limit_delay)
            
            response.raise_for_status()
            
            result = response.json()
            
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
            error_msg = f"Invalid API response format: {str(e)}"
            logger.error(f"API response parsing failed: {error_msg}")
            raise LMStudioAPIError(error_msg) from e
        except ValidationError as e:
            error_msg = f"Request validation error: {str(e)}"
            logger.error(f"Request validation failed: {error_msg}")
            raise LMStudioAPIError(error_msg) from e
    
    def _build_context_for_subtitle(
        self, 
        subtitles: List[Subtitle], 
        current_index: int,
        context_size: int = 5
    ) -> TranslationContext:
        """
        指定された字幕のコンテキストを構築.
        
        Args:
            subtitles: 全字幕リスト
            current_index: 現在の字幕インデックス
            context_size: コンテキストサイズ（前後何個まで含めるか）
            
        Returns:
            構築されたTranslationContext
        """
        # 前の字幕テキストを取得
        start_prev = max(0, current_index - context_size)
        previous_texts = [
            sub.text for sub in subtitles[start_prev:current_index]
        ]
        
        # 次の字幕テキストを取得
        end_next = min(len(subtitles), current_index + context_size + 1)
        next_texts = [
            sub.text for sub in subtitles[current_index + 1:end_next]
        ]
        
        return TranslationContext(
            previous_subtitles=previous_texts,
            next_subtitles=next_texts
        )
    
    async def translate_subtitles(
        self, 
        subtitles: List[Subtitle],
        batch_size: int = 5
    ) -> List[Subtitle]:
        """
        字幕リストを翻訳して返す.
        
        Args:
            subtitles: 翻訳対象の字幕リスト
            batch_size: バッチサイズ
            
        Returns:
            翻訳済みの字幕リスト
            
        Raises:
            TranslationError: 翻訳処理が失敗した場合
        """
        if not subtitles:
            return []
        
        translated_subtitles = []
        total_count = len(subtitles)
        
        logger.info(f"字幕翻訳を開始: {total_count}件")
        
        try:
            # バッチ処理で翻訳
            for i in range(0, total_count, batch_size):
                batch = subtitles[i:i + batch_size]
                batch_tasks = []
                
                for j, subtitle in enumerate(batch):
                    current_index = i + j
                    context = self._build_context_for_subtitle(subtitles, current_index)
                    
                    # 翻訳タスクを作成
                    task = self._translate_single_subtitle(subtitle, context)
                    batch_tasks.append(task)
                
                # バッチを並列実行
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # 結果を処理
                for subtitle, result in zip(batch, batch_results):
                    if isinstance(result, Exception):
                        logger.error(f"字幕 {subtitle.index} の翻訳に失敗: {str(result)}")
                        # 元のテキストを保持
                        translated_subtitles.append(subtitle)
                    else:
                        translated_subtitles.append(result)
                
                # 進捗ログ
                completed = min(i + batch_size, total_count)
                logger.info(f"翻訳進捗: {completed}/{total_count} ({completed/total_count*100:.1f}%)")
        
        except Exception as e:
            logger.error(f"バッチ翻訳処理でエラーが発生: {str(e)}")
            raise TranslationError(f"翻訳処理が失敗しました: {str(e)}") from e
        
        logger.info(f"字幕翻訳が完了: {len(translated_subtitles)}件")
        return translated_subtitles
    
    async def _translate_single_subtitle(
        self, 
        subtitle: Subtitle, 
        context: TranslationContext
    ) -> Subtitle:
        """
        単一字幕を翻訳.
        
        Args:
            subtitle: 翻訳対象の字幕
            context: 翻訳コンテキスト
            
        Returns:
            翻訳済みの字幕
        """
        prompt = self.build_prompt(subtitle.text, context)
        translated_text = await self._make_api_request(prompt)
        
        # 翻訳結果で新しい字幕オブジェクトを作成
        return Subtitle(
            index=subtitle.index,
            start_time=subtitle.start_time,
            end_time=subtitle.end_time, 
            text=translated_text
        )
    
    async def translate_batch(
        self, 
        texts: List[str], 
        context: Dict[str, any] = None
    ) -> List[str]:
        """
        テキストのバッチ翻訳（レガシー互換性のため）.
        
        Args:
            texts: 翻訳対象のテキストリスト
            context: コンテキスト情報
            
        Returns:
            翻訳済みテキストリスト
        """
        if not texts:
            return []
        
        context_obj = TranslationContext()
        if context:
            context_obj = TranslationContext(**context)
        
        tasks = []
        for text in texts:
            prompt = self.build_prompt(text, context_obj)
            task = self._make_api_request(prompt)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        translated_texts = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"テキスト {i} の翻訳に失敗: {str(result)}")
                translated_texts.append(texts[i])  # 元のテキストを保持
            else:
                translated_texts.append(result)
        
        return translated_texts
    
    async def health_check(self) -> bool:
        """
        LM Studio APIの接続確認.
        
        Returns:
            接続可能な場合True
        """
        try:
            test_request = TranslationRequest(
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=10
            )
            
            api_url = urljoin(self.base_url, "/v1/chat/completions")
            
            response = await self.client.post(
                api_url,
                json=test_request.model_dump(),
                headers={"Content-Type": "application/json"}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False