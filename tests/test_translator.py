"""翻訳モジュールのテスト."""

import asyncio
import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import pytest_asyncio

from modules.models import Subtitle, TranslationContext
from modules.translator import Translator, TranslationError, LMStudioAPIError


class TestTranslator:
    """Translatorクラスのテスト."""
    
    def setup_method(self):
        """各テストメソッドの前に実行される初期化."""
        self.translator = Translator(
            lm_studio_url="http://localhost:1234",
            model_name="test-model",
            max_concurrent_requests=2,
            request_timeout=10.0,
            rate_limit_delay=0.1
        )
    
    def teardown_method(self):
        """各テストメソッドの後に実行されるクリーンアップ."""
        # async fixtureがクリーンアップを担当するのでここでは何もしない
        pass
    
    def test_init(self):
        """初期化のテスト."""
        translator = Translator("http://localhost:1234", "test-model")
        
        assert translator.base_url == "http://localhost:1234"
        assert translator.model == "test-model"
        assert translator.max_concurrent_requests == 3  # デフォルト値
        assert translator.request_timeout == 30.0  # デフォルト値
    
    def test_init_with_trailing_slash(self):
        """末尾スラッシュありのURL初期化テスト."""
        translator = Translator("http://localhost:1234/", "test-model")
        assert translator.base_url == "http://localhost:1234"
    
    def test_build_prompt_basic(self):
        """基本的なプロンプト構築のテスト."""
        context = TranslationContext()
        current_text = "Hello, world!"
        
        prompt = self.translator.build_prompt(current_text, context)
        
        assert "Hello, world!" in prompt
        assert "これは映像コンテンツのSRT字幕データです" in prompt
        assert "翻訳対象:" in prompt
    
    def test_build_prompt_with_context(self):
        """コンテキスト付きプロンプト構築のテスト."""
        context = TranslationContext(
            previous_subtitles=["Previous 1", "Previous 2"],
            next_subtitles=["Next 1", "Next 2"],
            scene_description="A conversation scene",
            speaker_info="Main character speaking"
        )
        current_text = "Hello, world!"
        
        prompt = self.translator.build_prompt(current_text, context)
        
        assert "Hello, world!" in prompt
        assert "Previous 1" in prompt
        assert "Previous 2" in prompt
        assert "Next 1" in prompt
        assert "Next 2" in prompt
        assert "A conversation scene" in prompt
        assert "Main character speaking" in prompt
        assert "前の文脈:" in prompt
        assert "次の文脈:" in prompt
        assert "シーン情報:" in prompt
        assert "話者情報:" in prompt
    
    def test_build_context_for_subtitle_middle(self):
        """中間位置の字幕のコンテキスト構築テスト."""
        subtitles = [
            Subtitle(index=1, start_time=timedelta(seconds=0), end_time=timedelta(seconds=2), text="Text 1"),
            Subtitle(index=2, start_time=timedelta(seconds=2), end_time=timedelta(seconds=4), text="Text 2"),
            Subtitle(index=3, start_time=timedelta(seconds=4), end_time=timedelta(seconds=6), text="Text 3"),
            Subtitle(index=4, start_time=timedelta(seconds=6), end_time=timedelta(seconds=8), text="Text 4"),
            Subtitle(index=5, start_time=timedelta(seconds=8), end_time=timedelta(seconds=10), text="Text 5"),
        ]
        
        context = self.translator._build_context_for_subtitle(subtitles, 2, context_size=2)
        
        assert context.previous_subtitles == ["Text 1", "Text 2"]
        assert context.next_subtitles == ["Text 4", "Text 5"]
    
    def test_build_context_for_subtitle_beginning(self):
        """開始位置の字幕のコンテキスト構築テスト."""
        subtitles = [
            Subtitle(index=1, start_time=timedelta(seconds=0), end_time=timedelta(seconds=2), text="Text 1"),
            Subtitle(index=2, start_time=timedelta(seconds=2), end_time=timedelta(seconds=4), text="Text 2"),
            Subtitle(index=3, start_time=timedelta(seconds=4), end_time=timedelta(seconds=6), text="Text 3"),
        ]
        
        context = self.translator._build_context_for_subtitle(subtitles, 0, context_size=2)
        
        assert context.previous_subtitles == []
        assert context.next_subtitles == ["Text 2", "Text 3"]
    
    def test_build_context_for_subtitle_end(self):
        """終了位置の字幕のコンテキスト構築テスト."""
        subtitles = [
            Subtitle(index=1, start_time=timedelta(seconds=0), end_time=timedelta(seconds=2), text="Text 1"),
            Subtitle(index=2, start_time=timedelta(seconds=2), end_time=timedelta(seconds=4), text="Text 2"),
            Subtitle(index=3, start_time=timedelta(seconds=4), end_time=timedelta(seconds=6), text="Text 3"),
        ]
        
        context = self.translator._build_context_for_subtitle(subtitles, 2, context_size=2)
        
        assert context.previous_subtitles == ["Text 1", "Text 2"]
        assert context.next_subtitles == []


class TestTranslatorAsyncMethods:
    """Translatorの非同期メソッドのテスト."""
    
    @pytest_asyncio.fixture
    async def translator(self):
        """テスト用Translatorインスタンス."""
        translator = Translator(
            lm_studio_url="http://localhost:1234",
            model_name="test-model",
            request_timeout=5.0,
            rate_limit_delay=0.0  # テスト高速化のため遅延なし
        )
        yield translator
        await translator.client.aclose()
    
    @pytest.mark.asyncio
    async def test_make_api_request_success(self, translator):
        """成功時のAPI呼び出しテスト."""
        mock_response = {
            "choices": [
                {"message": {"content": "こんにちは、世界！"}}
            ]
        }
        
        with patch.object(translator.client, 'post') as mock_post:
            # レスポンスオブジェクトを作成（jsonは同期メソッド）
            mock_response_obj = AsyncMock()
            mock_response_obj.raise_for_status = MagicMock()  # 同期メソッド
            mock_response_obj.json = MagicMock(return_value=mock_response)  # 同期メソッド
            
            mock_post.return_value = mock_response_obj
            
            result = await translator._make_api_request("Hello, world!")
            
            assert result == "こんにちは、世界！"
            mock_post.assert_called_once()
            
            # リクエストの内容を確認
            call_args = mock_post.call_args
            request_json = call_args[1]['json']
            assert request_json['model'] == 'test-model'
            assert len(request_json['messages']) == 2
            assert request_json['messages'][1]['content'] == "Hello, world!"
    
    @pytest.mark.asyncio
    async def test_make_api_request_http_error(self, translator):
        """HTTP エラー時のAPI呼び出しテスト."""
        with patch.object(translator.client, 'post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            
            mock_response_obj = AsyncMock()
            mock_response_obj.raise_for_status = MagicMock(
                side_effect=httpx.HTTPStatusError(
                    "500 Server Error", request=MagicMock(), response=mock_response
                )
            )
            
            mock_post.return_value = mock_response_obj
            
            with pytest.raises(LMStudioAPIError) as exc_info:
                await translator._make_api_request("Hello, world!")
            
            assert "HTTP Error 500" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_make_api_request_connection_error(self, translator):
        """接続エラー時のAPI呼び出しテスト."""
        with patch.object(translator.client, 'post') as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")
            
            with pytest.raises(LMStudioAPIError) as exc_info:
                await translator._make_api_request("Hello, world!")
            
            assert "Request Error" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_make_api_request_invalid_response(self, translator):
        """不正なレスポンス時のAPI呼び出しテスト."""
        with patch.object(translator.client, 'post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.raise_for_status = MagicMock()  # 同期メソッド
            mock_response_obj.json = MagicMock(return_value={"invalid": "response"})  # 同期メソッド
            
            mock_post.return_value = mock_response_obj
            
            with pytest.raises(LMStudioAPIError) as exc_info:
                await translator._make_api_request("Hello, world!")
            
            assert "APIレスポンスにchoicesが含まれていません" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_translate_single_subtitle(self, translator):
        """単一字幕翻訳のテスト."""
        subtitle = Subtitle(
            index=1,
            start_time=timedelta(seconds=0),
            end_time=timedelta(seconds=2),
            text="Hello, world!"
        )
        context = TranslationContext()
        
        with patch.object(translator, '_make_api_request') as mock_api:
            mock_api.return_value = "こんにちは、世界！"
            
            result = await translator._translate_single_subtitle(subtitle, context)
            
            assert result.index == 1
            assert result.start_time == timedelta(seconds=0)
            assert result.end_time == timedelta(seconds=2)
            assert result.text == "こんにちは、世界！"
    
    @pytest.mark.asyncio
    async def test_translate_subtitles_success(self, translator):
        """字幕リスト翻訳成功のテスト."""
        subtitles = [
            Subtitle(index=1, start_time=timedelta(seconds=0), end_time=timedelta(seconds=2), text="Hello"),
            Subtitle(index=2, start_time=timedelta(seconds=2), end_time=timedelta(seconds=4), text="World"),
        ]
        
        with patch.object(translator, '_make_api_request') as mock_api:
            mock_api.side_effect = ["こんにちは", "世界"]
            
            results = await translator.translate_subtitles(subtitles, batch_size=2)
            
            assert len(results) == 2
            assert results[0].text == "こんにちは"
            assert results[1].text == "世界"
            assert mock_api.call_count == 2
    
    @pytest.mark.asyncio
    async def test_translate_subtitles_empty_list(self, translator):
        """空リスト翻訳のテスト."""
        result = await translator.translate_subtitles([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_translate_subtitles_with_error(self, translator):
        """エラー発生時の字幕翻訳テスト."""
        subtitles = [
            Subtitle(index=1, start_time=timedelta(seconds=0), end_time=timedelta(seconds=2), text="Hello"),
            Subtitle(index=2, start_time=timedelta(seconds=2), end_time=timedelta(seconds=4), text="World"),
        ]
        
        with patch.object(translator, '_make_api_request') as mock_api:
            mock_api.side_effect = ["こんにちは", Exception("API Error")]
            
            results = await translator.translate_subtitles(subtitles, batch_size=2)
            
            assert len(results) == 2
            assert results[0].text == "こんにちは"
            assert results[1].text == "World"  # エラー時は元のテキストを保持
    
    @pytest.mark.asyncio
    async def test_translate_batch_success(self, translator):
        """バッチ翻訳成功のテスト."""
        texts = ["Hello", "World"]
        
        with patch.object(translator, '_make_api_request') as mock_api:
            mock_api.side_effect = ["こんにちは", "世界"]
            
            results = await translator.translate_batch(texts)
            
            assert results == ["こんにちは", "世界"]
            assert mock_api.call_count == 2
    
    @pytest.mark.asyncio
    async def test_translate_batch_with_context(self, translator):
        """コンテキスト付きバッチ翻訳のテスト."""
        texts = ["Hello"]
        context = {
            "previous_subtitles": ["Previous text"],
            "next_subtitles": ["Next text"]
        }
        
        with patch.object(translator, '_make_api_request') as mock_api:
            mock_api.return_value = "こんにちは"
            
            results = await translator.translate_batch(texts, context)
            
            assert results == ["こんにちは"]
            mock_api.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_translate_batch_empty_list(self, translator):
        """空リストバッチ翻訳のテスト."""
        result = await translator.translate_batch([])
        assert result == []
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, translator):
        """ヘルスチェック成功のテスト."""
        with patch.object(translator.client, 'post') as mock_post:
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            
            mock_post.return_value = mock_response_obj
            
            result = await translator.health_check()
            
            assert result is True
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_check_failure(self, translator):
        """ヘルスチェック失敗のテスト."""
        with patch.object(translator.client, 'post') as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")
            
            result = await translator.health_check()
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """コンテキストマネージャーのテスト."""
        async with Translator("http://localhost:1234", "test-model") as translator:
            assert translator.client is not None
        
        # コンテキスト終了後はクライアントが閉じられる
        assert translator.client.is_closed


def test_subtitle_model():
    """Subtitleモデルのテスト."""
    subtitle = Subtitle(
        index=1,
        start_time=timedelta(seconds=0),
        end_time=timedelta(seconds=5),
        text="Test subtitle"
    )
    
    assert subtitle.duration() == timedelta(seconds=5)
    assert "1: 0:00:00 -> 0:00:05 | Test subtitle" in str(subtitle)


def test_translation_context_model():
    """TranslationContextモデルのテスト."""
    context = TranslationContext(
        previous_subtitles=["Previous 1", "Previous 2"],
        next_subtitles=["Next 1"],
        scene_description="Scene description",
        speaker_info="Speaker info"
    )
    
    assert len(context.previous_subtitles) == 2
    assert len(context.next_subtitles) == 1
    assert context.scene_description == "Scene description"
    assert context.speaker_info == "Speaker info"


def test_translation_context_default():
    """TranslationContextデフォルト値のテスト."""
    context = TranslationContext()
    
    assert context.previous_subtitles == []
    assert context.next_subtitles == []
    assert context.scene_description is None
    assert context.speaker_info is None