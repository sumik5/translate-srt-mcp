#!/usr/bin/env python3
"""
SRT翻訳MCPサーバー
fastmcp最新版を使用したMCPサーバー実装

使用例:
1. 基本的な翻訳:
   translated = translate_srt(srt_content=content)
   
2. カスタム設定:
   translated = translate_srt(
       srt_content=content,
       model_name="llama-3.2-3b",
       chunk_size=500
   )
"""

import os
import sys
import logging
import re
import json
from pathlib import Path
from typing import Optional, List, Tuple, Dict
from datetime import datetime

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
mcp = FastMCP(
    "translate-srt",
    description="SRT字幕ファイルを日本語に翻訳するMCPサーバー。LM Studioの翻訳モデルを使用して高品質な字幕翻訳を提供します。"
)

# 翻訳統計を保持
translation_stats = {
    "total_translations": 0,
    "total_characters": 0,
    "total_subtitles": 0,
    "last_translation": None,
    "errors": 0
}

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

@mcp.tool(
    description="""SRT字幕テキストを日本語に翻訳してSRT形式のデータを返す。

使用例:
1. ファイルから読み込んで翻訳:
   srt_content = read_file("movie.srt")
   translated = translate_srt(srt_content=srt_content)
   write_file("movie_ja.srt", translated)
   
2. カスタム設定で翻訳:
   translated = translate_srt(
       srt_content=srt_content,
       model_name="llama-3.2-3b",
       chunk_size=500
   )

注意事項:
- LM Studioが起動している必要があります
- model_nameを指定しない場合は環境変数LM_MODEL_NAMEが必要です
- 大きなファイルはchunk_sizeで分割処理されます
- タイムスタンプは保持されます"""
)
async def translate_srt(
    srt_content: str,
    lm_studio_url: Optional[str] = None,
    model_name: Optional[str] = None,
    chunk_size: Optional[int] = None,
    preserve_formatting: bool = True
) -> str:
    """
    SRT字幕テキストを日本語に翻訳してSRT形式のデータを返す
    
    Args:
        srt_content: 翻訳対象のSRT形式テキスト
        lm_studio_url: LM StudioのAPI URL (省略時は環境変数LM_STUDIO_URLを使用)
        model_name: 使用する翻訳モデル名 (省略時は環境変数LM_MODEL_NAMEを使用)
        chunk_size: チャンクサイズ (省略時は環境変数CHUNK_SIZEまたはデフォルト1000を使用)
        preserve_formatting: 元の書式（改行、スペース等）を保持するか
        
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
    
    # 統計情報を更新
    global translation_stats
    translation_stats["total_translations"] += 1
    translation_stats["last_translation"] = datetime.now().isoformat()
    
    logger.info(f"Translation started (Translation #{translation_stats['total_translations']})")
    logger.info(f"LM Studio URL: {lm_studio_url}")
    logger.info(f"Model: {model_name}")
    logger.info(f"Input length: {len(srt_content)} characters")
    logger.info(f"Preserve formatting: {preserve_formatting}")
    
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
        
        # 統計情報を更新
        translation_stats["total_characters"] += len(srt_content)
        translation_stats["total_subtitles"] += len(parse_srt_string(srt_content))
        
        logger.info(f"Translation completed successfully")
        logger.info(f"Output length: {len(result)} characters")
        return result
        
    except Exception as e:
        translation_stats["errors"] += 1
        logger.error(f"Translation failed: {e}")
        raise RuntimeError(f"Translation process failed: {str(e)}") from e

@mcp.tool(
    description="サーバー情報と統計を取得"
)
async def get_server_info() -> dict:
    """
    サーバー情報と統計を取得
    
    Returns:
        dict: サーバーの名前、バージョン、統計情報
    """
    return {
        "name": "translate-srt",
        "version": "0.2.0",
        "description": "SRT subtitle translation MCP server with LM Studio integration",
        "fastmcp_version": "2.11.3",
        "configuration": {
            "default_lm_studio_url": DEFAULT_LM_STUDIO_URL,
            "default_model_name": DEFAULT_MODEL_NAME or "(not set - must provide)",
            "default_chunk_size": DEFAULT_CHUNK_SIZE
        },
        "statistics": translation_stats,
        "capabilities": [
            "SRT format parsing and generation",
            "Chunk-based translation for large files",
            "Preserve timing information",
            "Support for multi-line subtitles",
            "Automatic retry on failure",
            "LM Studio integration"
        ],
        "supported_languages": {
            "source": "Any (auto-detect)",
            "target": "Japanese"
        }
    }

@mcp.tool(
    description="""SRTファイルの検証と分析を行う。
    字幕数、総時間、平均文字数などの統計情報を提供します。"""
)
async def analyze_srt(
    srt_content: str,
    detailed: bool = False
) -> dict:
    """
    SRTファイルの内容を分析
    
    Args:
        srt_content: 分析対象のSRT形式テキスト
        detailed: 詳細分析を行うか
        
    Returns:
        dict: 分析結果
    """
    try:
        entries = parse_srt_string(srt_content)
        
        if not entries:
            return {
                "valid": False,
                "error": "No valid SRT entries found",
                "subtitle_count": 0
            }
        
        # 基本統計
        subtitle_count = len(entries)
        total_chars = sum(len(entry[3]) for entry in entries)
        avg_chars = total_chars / subtitle_count if subtitle_count > 0 else 0
        
        # 時間計算
        def parse_time(time_str: str) -> float:
            """時間文字列を秒に変換"""
            parts = time_str.replace(',', '.').split(':')
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        
        first_start = parse_time(entries[0][1])
        last_end = parse_time(entries[-1][2])
        total_duration = last_end - first_start
        
        result = {
            "valid": True,
            "subtitle_count": subtitle_count,
            "total_characters": total_chars,
            "average_characters": round(avg_chars, 1),
            "total_duration_seconds": round(total_duration, 2),
            "duration_formatted": f"{int(total_duration//60)}:{int(total_duration%60):02d}",
            "first_timestamp": entries[0][1],
            "last_timestamp": entries[-1][2]
        }
        
        if detailed:
            # 詳細分析
            line_counts = [len(entry[3].split('\n')) for entry in entries]
            char_counts = [len(entry[3]) for entry in entries]
            
            result["detailed_stats"] = {
                "max_lines_per_subtitle": max(line_counts),
                "avg_lines_per_subtitle": round(sum(line_counts) / len(line_counts), 1),
                "max_characters": max(char_counts),
                "min_characters": min(char_counts),
                "empty_subtitles": sum(1 for c in char_counts if c == 0),
                "multi_line_subtitles": sum(1 for l in line_counts if l > 1)
            }
            
            # 言語検出（簡易版）
            text_sample = ' '.join(entry[3] for entry in entries[:50])  # 最初の50個をサンプル
            has_japanese = bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]', text_sample))
            has_english = bool(re.search(r'[a-zA-Z]{3,}', text_sample))
            
            result["detected_languages"] = {
                "japanese": has_japanese,
                "english": has_english,
                "other": not (has_japanese or has_english)
            }
        
        return result
        
    except Exception as e:
        return {
            "valid": False,
            "error": f"Analysis failed: {str(e)}",
            "subtitle_count": 0
        }

@mcp.tool(
    description="""LM Studioの接続状態を確認する。
    APIの到達可能性とモデルの利用可能性をチェックします。"""
)
async def check_lm_studio_status(
    lm_studio_url: Optional[str] = None,
    model_name: Optional[str] = None
) -> dict:
    """
    LM Studioの接続状態を確認
    
    Args:
        lm_studio_url: LM StudioのAPI URL (省略時は環境変数を使用)
        model_name: 確認するモデル名 (省略時は環境変数を使用)
        
    Returns:
        dict: 接続状態とモデル情報
    """
    import httpx
    
    # デフォルト値を使用
    if lm_studio_url is None:
        lm_studio_url = DEFAULT_LM_STUDIO_URL
    if model_name is None:
        model_name = DEFAULT_MODEL_NAME
    
    # URLの整形
    base_url = lm_studio_url.rstrip('/')
    if '/v1' not in base_url:
        base_url = base_url + '/v1'
    
    result = {
        "lm_studio_url": base_url,
        "model_name": model_name or "(not configured)",
        "api_reachable": False,
        "models_endpoint_available": False,
        "model_available": False,
        "available_models": [],
        "error": None
    }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # APIの到達可能性を確認
            try:
                response = await client.get(f"{base_url}/models")
                response.raise_for_status()
                result["api_reachable"] = True
                result["models_endpoint_available"] = True
                
                # 利用可能なモデルのリストを取得
                models_data = response.json()
                if "data" in models_data:
                    available_models = [model["id"] for model in models_data["data"]]
                    result["available_models"] = available_models
                    
                    # 指定されたモデルが利用可能か確認
                    if model_name and model_name in available_models:
                        result["model_available"] = True
                    elif model_name:
                        result["error"] = f"Model '{model_name}' not found in available models"
                
            except httpx.HTTPStatusError as e:
                result["error"] = f"HTTP Error {e.response.status_code}: Unable to reach models endpoint"
            except httpx.RequestError as e:
                result["error"] = f"Connection Error: {str(e)}"
                
    except Exception as e:
        result["error"] = f"Unexpected error: {str(e)}"
    
    # 推奨事項を追加
    if not result["api_reachable"]:
        result["recommendation"] = "Please ensure LM Studio is running and accessible at the specified URL"
    elif not result["models_endpoint_available"]:
        result["recommendation"] = "LM Studio is reachable but the models endpoint is not available"
    elif not result["model_available"] and model_name:
        result["recommendation"] = f"Please load the model '{model_name}' in LM Studio or use one of the available models: {', '.join(result['available_models'][:3])}"
    else:
        result["recommendation"] = "LM Studio is properly configured and ready for translation"
    
    return result

@mcp.tool(
    description="""字幕の簡易プレビューを生成する。
    最初と最後の数個の字幕を表示して内容を確認できます。"""
)
async def preview_srt(
    srt_content: str,
    num_entries: int = 5,
    show_start: bool = True,
    show_end: bool = True
) -> dict:
    """
    SRT字幕のプレビューを生成
    
    Args:
        srt_content: プレビュー対象のSRT形式テキスト
        num_entries: 表示する字幕の数（開始と終了それぞれ）
        show_start: 最初の字幕を表示するか
        show_end: 最後の字幕を表示するか
        
    Returns:
        dict: プレビュー結果
    """
    try:
        entries = parse_srt_string(srt_content)
        
        if not entries:
            return {
                "success": False,
                "error": "No valid SRT entries found",
                "total_entries": 0
            }
        
        preview = {
            "success": True,
            "total_entries": len(entries),
            "preview_entries": {}
        }
        
        # 開始部分のプレビュー
        if show_start:
            start_entries = []
            for i in range(min(num_entries, len(entries))):
                entry = entries[i]
                start_entries.append({
                    "index": entry[0],
                    "time": f"{entry[1]} --> {entry[2]}",
                    "text": entry[3],
                    "char_count": len(entry[3])
                })
            preview["preview_entries"]["start"] = start_entries
        
        # 終了部分のプレビュー
        if show_end and len(entries) > num_entries:
            end_entries = []
            start_idx = max(0, len(entries) - num_entries)
            for i in range(start_idx, len(entries)):
                entry = entries[i]
                end_entries.append({
                    "index": entry[0],
                    "time": f"{entry[1]} --> {entry[2]}",
                    "text": entry[3],
                    "char_count": len(entry[3])
                })
            preview["preview_entries"]["end"] = end_entries
        
        # 中間部分のサンプル（オプション）
        if len(entries) > num_entries * 3:
            middle_idx = len(entries) // 2
            middle_entry = entries[middle_idx]
            preview["preview_entries"]["middle_sample"] = {
                "index": middle_entry[0],
                "time": f"{middle_entry[1]} --> {middle_entry[2]}",
                "text": middle_entry[3],
                "char_count": len(middle_entry[3])
            }
        
        return preview
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Preview generation failed: {str(e)}",
            "total_entries": 0
        }

def main():
    """メインエントリーポイント"""
    # MCPサーバーを起動（stdioトランスポート使用）
    mcp.run()

if __name__ == "__main__":
    main()