#!/usr/bin/env python3
"""
SRT翻訳MCPサーバー
fastmcp最新版を使用したMCPサーバー実装
"""

import os
import sys
import logging
import re
from pathlib import Path
from typing import Optional, List, Tuple

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP

# モジュールインポート
from modules.srt_parser import SRTParser, Subtitle
from modules.translator import Translator

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 環境変数からデフォルト値を取得
DEFAULT_LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', 'http://localhost:1234/v1')
DEFAULT_MODEL_NAME = os.getenv('LM_MODEL_NAME', '')
DEFAULT_CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '1000'))

# FastMCPサーバーインスタンスを作成
mcp = FastMCP("translate-srt")

def parse_srt_string(srt_content: str) -> List[Tuple[int, str, str, str]]:
    """
    SRT文字列をパースして字幕エントリのリストを返す
    
    Returns:
        List of tuples: (index, start_time, end_time, text)
    """
    entries = []
    blocks = re.split(r'\n\s*\n', srt_content.strip())
    
    for block in blocks:
        if not block.strip():
            continue
        
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        
        try:
            # インデックス
            index = int(lines[0].strip())
            
            # タイムコード
            time_match = re.match(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[1])
            if not time_match:
                continue
            
            start_time, end_time = time_match.groups()
            
            # テキスト
            text = '\n'.join(lines[2:])
            
            entries.append((index, start_time, end_time, text))
            
        except (ValueError, IndexError):
            continue
    
    return entries

def split_srt_into_chunks(srt_content: str, chunk_size: int) -> List[str]:
    """
    SRT文字列をチャンクに分割（字幕ブロックを分断しない）
    
    Args:
        srt_content: SRT形式の文字列
        chunk_size: 各チャンクの最大文字数
        
    Returns:
        チャンクに分割されたSRT文字列のリスト
    """
    entries = parse_srt_string(srt_content)
    
    if not entries:
        return [srt_content]
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for entry in entries:
        index, start_time, end_time, text = entry
        
        # エントリーをSRT形式に変換
        entry_text = f"{index}\n{start_time} --> {end_time}\n{text}\n\n"
        entry_size = len(entry_text)
        
        # チャンクサイズを超えそうな場合、現在のチャンクを保存して新しいチャンクを開始
        if current_size + entry_size > chunk_size and current_chunk:
            chunks.append(''.join(current_chunk).strip())
            current_chunk = []
            current_size = 0
        
        current_chunk.append(entry_text)
        current_size += entry_size
    
    # 最後のチャンクを追加
    if current_chunk:
        chunks.append(''.join(current_chunk).strip())
    
    return chunks if chunks else [srt_content]

def merge_translated_chunks(translated_chunks: List[str]) -> str:
    """
    翻訳されたチャンクを結合して1つのSRT文字列にする
    """
    # 各チャンクの最後に空行を追加して結合
    merged = '\n\n'.join(chunk.strip() for chunk in translated_chunks if chunk.strip())
    return merged

@mcp.tool()
async def translate_srt(
    srt_content: str,
    lm_studio_url: Optional[str] = None,
    model_name: Optional[str] = None,
    chunk_size: Optional[int] = None
) -> str:
    """
    SRT字幕テキストを日本語に翻訳してSRT形式のデータを返す
    
    Args:
        srt_content: 翻訳対象のSRT形式テキスト
        lm_studio_url: LM StudioのAPI URL (省略時は環境変数LM_STUDIO_URLを使用)
        model_name: 使用する翻訳モデル名 (省略時は環境変数LM_MODEL_NAMEを使用)
        chunk_size: チャンクサイズ (省略時は環境変数CHUNK_SIZEまたはデフォルト1000を使用)
        
    Returns:
        str: 翻訳結果のSRT形式データ
        
    Raises:
        ValueError: 無効なパラメータが指定された、またはモデル名が環境変数に設定されていない
        ConnectionError: LM StudioのAPIに接続できない
        RuntimeError: 翻訳処理中にエラーが発生した
    """
    # デフォルト値を使用
    if lm_studio_url is None:
        lm_studio_url = DEFAULT_LM_STUDIO_URL
        logger.info(f"Using LM Studio URL from environment: {lm_studio_url}")
    
    if model_name is None:
        model_name = DEFAULT_MODEL_NAME
        if not model_name:
            raise ValueError("Model name is required. Set LM_MODEL_NAME environment variable or provide model_name parameter.")
        logger.info(f"Using model from environment: {model_name}")
    
    if chunk_size is None:
        chunk_size = DEFAULT_CHUNK_SIZE
        logger.info(f"Using chunk size: {chunk_size}")
    
    logger.info(f"Translation started")
    logger.info(f"LM Studio URL: {lm_studio_url}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Input length: {len(srt_content)} characters")
    
    try:
        # SRT文字列をチャンクに分割
        chunks = split_srt_into_chunks(srt_content, chunk_size)
        logger.info(f"Split into {len(chunks)} chunks")
        
        # 各チャンクを翻訳
        translator = Translator(
            lm_studio_url=lm_studio_url,
            model_name=model_name
        )
        
        translated_chunks = []
        for i, chunk in enumerate(chunks, 1):
            logger.info(f"Translating chunk {i}/{len(chunks)} ({len(chunk)} characters)...")
            
            # SRTパーサーを使用してSubtitleオブジェクトに変換
            srt_parser = SRTParser()
            
            # 一時的にチャンクをファイルに保存せずに処理
            # parse_srtメソッドをオーバーライドする代わりに、直接Subtitleオブジェクトを作成
            entries = parse_srt_string(chunk)
            subtitles = []
            for index, start_time, end_time, text in entries:
                subtitles.append(Subtitle(
                    index=index,
                    start_time=start_time,
                    end_time=end_time,
                    text=text
                ))
            
            # 翻訳実行
            if subtitles:
                translated_subtitles = await translator.translate_subtitles(subtitles)
                
                # 翻訳結果をSRT形式に変換
                translated_chunk = srt_parser.generate_srt_string(translated_subtitles)
                translated_chunks.append(translated_chunk)
            else:
                # 空のチャンクの場合はそのまま追加
                translated_chunks.append(chunk)
        
        # 翻訳されたチャンクを結合
        result = merge_translated_chunks(translated_chunks)
        
        logger.info(f"Translation completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise RuntimeError(f"Translation process failed: {str(e)}") from e

@mcp.tool()
async def get_server_info() -> dict:
    """
    サーバー情報を取得
    
    Returns:
        dict: サーバーの名前とバージョン情報
    """
    return {
        "name": "translate-srt",
        "version": "0.1.0",
        "description": "SRT subtitle translation MCP server",
        "fastmcp_version": "2.11.3",
        "default_chunk_size": DEFAULT_CHUNK_SIZE
    }

def main():
    """メインエントリーポイント"""
    # MCPサーバーを起動（stdioトランスポート使用）
    mcp.run()

if __name__ == "__main__":
    main()