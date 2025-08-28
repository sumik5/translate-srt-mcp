"""
SRTファイルの解析と生成を行うモジュール

このモジュールはSRT (SubRip) 形式の字幕ファイルを解析し、
字幕オブジェクトとして管理し、再びSRT形式で出力する機能を提供する。
"""

import re
import chardet
from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Subtitle:
    """字幕エントリを表すデータクラス
    
    Attributes:
        index (int): 字幕の番号（1から開始）
        start_time (str): 開始時刻（HH:MM:SS,mmm形式）
        end_time (str): 終了時刻（HH:MM:SS,mmm形式）
        text (str): 字幕テキスト（改行を含む可能性がある）
    """
    index: int
    start_time: str
    end_time: str
    text: str


class SRTParser:
    """SRTファイルの解析と生成を行うクラス"""
    
    # タイムスタンプの正規表現パターン
    TIME_PATTERN = re.compile(
        r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})'
    )
    
    def __init__(self):
        """SRTParserのインスタンスを初期化する"""
        pass
    
    def detect_encoding(self, file_path: str) -> str:
        """ファイルのエンコーディングを検出する
        
        Args:
            file_path (str): ファイルパス
            
        Returns:
            str: 検出されたエンコーディング（UTF-8を優先）
            
        Raises:
            FileNotFoundError: ファイルが存在しない場合
            IOError: ファイル読み込みエラーの場合
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                
            # chardetを使用してエンコーディングを検出
            detected = chardet.detect(raw_data)
            encoding = detected['encoding'] if detected['encoding'] else 'utf-8'
            
            # UTF-8を優先する
            if encoding.lower() in ['ascii', 'utf-8']:
                return 'utf-8'
            
            return encoding
            
        except FileNotFoundError:
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")
        except Exception as e:
            raise IOError(f"ファイルの読み込みエラー: {e}")
    
    def parse_srt(self, file_path: str) -> List[Subtitle]:
        """SRTファイルを解析して字幕オブジェクトのリストを返す
        
        Args:
            file_path (str): SRTファイルのパス
            
        Returns:
            List[Subtitle]: 解析された字幕オブジェクトのリスト
            
        Raises:
            FileNotFoundError: ファイルが存在しない場合
            ValueError: SRT形式が不正な場合
            IOError: ファイル読み込みエラーの場合
        """
        encoding = self.detect_encoding(file_path)
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                content = f.read().strip()
        except Exception as e:
            raise IOError(f"ファイルの読み込みエラー: {e}")
        
        if not content:
            return []
        
        # 字幕エントリを分割（空行で区切られる）
        entries = re.split(r'\n\s*\n', content)
        subtitles = []
        
        for entry_index, entry in enumerate(entries, 1):
            if not entry.strip():
                continue
                
            lines = entry.strip().split('\n')
            
            if len(lines) < 3:
                continue  # 不完全なエントリはスキップ
            
            # 1行目: 字幕番号
            try:
                index = int(lines[0].strip())
            except (ValueError, IndexError):
                raise ValueError(f"字幕番号が不正です（エントリ {entry_index}）: {lines[0] if lines else 'empty'}")
            
            # 2行目: タイムスタンプ
            if len(lines) < 2:
                raise ValueError(f"タイムスタンプが見つかりません（エントリ {entry_index}）")
                
            time_match = self.TIME_PATTERN.match(lines[1].strip())
            if not time_match:
                raise ValueError(f"タイムスタンプ形式が不正です（エントリ {entry_index}）: {lines[1]}")
            
            start_time, end_time = time_match.groups()
            
            # 3行目以降: 字幕テキスト
            text_lines = lines[2:]
            text = '\n'.join(text_lines).strip()
            
            if not text:
                continue  # テキストが空の場合はスキップ
            
            subtitles.append(Subtitle(
                index=index,
                start_time=start_time,
                end_time=end_time,
                text=text
            ))
        
        return subtitles
    
    def save_srt(self, subtitles: List[Subtitle], file_path: str, encoding: str = 'utf-8') -> None:
        """字幕オブジェクトのリストからSRTファイルを生成する
        
        Args:
            subtitles (List[Subtitle]): 字幕オブジェクトのリスト
            file_path (str): 出力ファイルパス
            encoding (str): 出力ファイルのエンコーディング（デフォルト: utf-8）
            
        Raises:
            IOError: ファイル書き込みエラーの場合
            ValueError: 字幕データが不正な場合
        """
        if not subtitles:
            raise ValueError("字幕データが空です")
        
        # 字幕データの事前検証
        for i, subtitle in enumerate(subtitles):
            if not subtitle.start_time or not subtitle.end_time or not subtitle.text:
                raise ValueError(f"字幕データが不完全です（インデックス: {i}）")
        
        try:
            with open(file_path, 'w', encoding=encoding) as f:
                for i, subtitle in enumerate(subtitles):
                    # SRT形式で出力
                    f.write(f"{subtitle.index}\n")
                    f.write(f"{subtitle.start_time} --> {subtitle.end_time}\n")
                    f.write(f"{subtitle.text}")
                    
                    # 最後のエントリ以外は空行を2つ追加
                    if i < len(subtitles) - 1:
                        f.write("\n\n")
                        
        except ValueError:
            # ValueErrorは再発生
            raise
        except Exception as e:
            raise IOError(f"ファイルの書き込みエラー: {e}")
    
    def validate_time_format(self, time_str: str) -> bool:
        """時刻形式が正しいかを検証する
        
        Args:
            time_str (str): 時刻文字列（HH:MM:SS,mmm形式）
            
        Returns:
            bool: 形式が正しい場合はTrue
        """
        pattern = re.compile(r'^(\d{2}):(\d{2}):(\d{2}),(\d{3})$')
        match = pattern.match(time_str)
        if not match:
            return False
        
        # 時刻の範囲をチェック
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        
        if hours > 23 or minutes > 59 or seconds > 59 or milliseconds > 999:
            return False
        
        return True
    
    def format_time(self, hours: int, minutes: int, seconds: int, milliseconds: int) -> str:
        """時刻を SRT 形式の文字列に変換する
        
        Args:
            hours (int): 時間
            minutes (int): 分
            seconds (int): 秒
            milliseconds (int): ミリ秒
            
        Returns:
            str: SRT形式の時刻文字列
        """
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"
    
    def generate_srt_string(self, subtitles: List[Subtitle]) -> str:
        """字幕オブジェクトのリストからSRT形式の文字列を生成する
        
        Args:
            subtitles (List[Subtitle]): 字幕オブジェクトのリスト
            
        Returns:
            str: SRT形式の文字列データ
            
        Raises:
            ValueError: 字幕データが不正な場合
        """
        if not subtitles:
            raise ValueError("字幕データが空です")
        
        # 字幕データの事前検証
        for i, subtitle in enumerate(subtitles):
            if not subtitle.start_time or not subtitle.end_time or not subtitle.text:
                raise ValueError(f"字幕データが不完全です（インデックス: {i}）")
        
        srt_lines = []
        for i, subtitle in enumerate(subtitles):
            # SRT形式で追加
            srt_lines.append(str(subtitle.index))
            srt_lines.append(f"{subtitle.start_time} --> {subtitle.end_time}")
            srt_lines.append(subtitle.text)
            
            # 最後のエントリ以外は空行を追加
            if i < len(subtitles) - 1:
                srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    async def parse_file(self, file_path) -> List[Subtitle]:
        """SRTファイルを解析して字幕オブジェクトのリストを返す（非同期版）
        
        Args:
            file_path: ファイルパス（Path オブジェクトまたは文字列）
            
        Returns:
            List[Subtitle]: 解析された字幕オブジェクトのリスト
        """
        # pathlib.Path オブジェクトを文字列に変換
        return self.parse_srt(str(file_path))