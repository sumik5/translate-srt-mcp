#!/usr/bin/env python3
"""
SRT翻訳MCPサーバー
fastmcp最新版を使用したMCPサーバー実装
"""

import os
import sys
import logging
from pathlib import Path
from typing import Optional

# プロジェクトルートをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastmcp import FastMCP

# モジュールインポート
from modules.srt_parser import SRTParser
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

# FastMCPサーバーインスタンスを作成
mcp = FastMCP("translate-srt")

@mcp.tool()
async def translate_srt(
    srt_file_path: str,
    lm_studio_url: Optional[str] = None,
    model_name: Optional[str] = None
) -> str:
    """
    SRT字幕ファイルを日本語に翻訳してSRT形式のデータを返す
    
    Args:
        srt_file_path: 翻訳対象のSRTファイルパス
        lm_studio_url: LM StudioのAPI URL (省略時は環境変数LM_STUDIO_URLを使用)
        model_name: 使用する翻訳モデル名 (省略時は環境変数LM_MODEL_NAMEを使用)
        
    Returns:
        str: 翻訳結果のSRT形式データ
        
    Raises:
        FileNotFoundError: 指定されたSRTファイルが見つからない
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
    
    logger.info(f"Translation started: {srt_file_path}")
    logger.info(f"LM Studio URL: {lm_studio_url}")
    logger.info(f"Model: {model_name}")
    
    try:
        # ファイル存在確認
        input_path = Path(srt_file_path)
        if not input_path.exists():
            raise FileNotFoundError(f"SRT file not found: {srt_file_path}")
        
        # 1. SRTファイル解析
        logger.info("Parsing SRT file...")
        srt_parser = SRTParser()
        subtitles = await srt_parser.parse_file(input_path)
        logger.info(f"Found {len(subtitles)} subtitle entries")
        
        # 2. 翻訳実行
        logger.info("Starting translation process...")
        translator = Translator(
            lm_studio_url=lm_studio_url,
            model_name=model_name
        )
        translated_subtitles = await translator.translate_subtitles(subtitles)
        logger.info("Translation completed")
        
        # 3. SRT形式のデータを生成して返す
        logger.info("Generating SRT format data...")
        srt_data = srt_parser.generate_srt_string(translated_subtitles)
        
        logger.info(f"Translation completed successfully")
        return srt_data
        
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
        "fastmcp_version": "2.11.3"
    }

def main():
    """メインエントリーポイント"""
    # MCPサーバーを起動（stdioトランスポート使用）
    mcp.run()

if __name__ == "__main__":
    main()