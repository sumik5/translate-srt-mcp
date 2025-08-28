"""
SRTパーサーモジュールの単体テスト
"""

import os
import tempfile
import unittest
from typing import List
from pathlib import Path

from modules.srt_parser import SRTParser, Subtitle


class TestSRTParser(unittest.TestCase):
    """SRTParserクラスのテスト"""
    
    def setUp(self):
        """テストの前準備"""
        self.parser = SRTParser()
        self.test_dir = Path(__file__).parent
        self.sample_srt = self.test_dir / "sample.srt"
    
    def test_parse_srt_basic(self):
        """基本的なSRT解析のテスト"""
        subtitles = self.parser.parse_srt(str(self.sample_srt))
        
        # 字幕数の確認
        self.assertEqual(len(subtitles), 4)
        
        # 1つ目の字幕の確認
        first_subtitle = subtitles[0]
        self.assertEqual(first_subtitle.index, 1)
        self.assertEqual(first_subtitle.start_time, "00:00:01,000")
        self.assertEqual(first_subtitle.end_time, "00:00:04,000")
        self.assertEqual(first_subtitle.text, "Hello, world!\nThis is a test subtitle.")
        
        # 2つ目の字幕の確認
        second_subtitle = subtitles[1]
        self.assertEqual(second_subtitle.index, 2)
        self.assertEqual(second_subtitle.start_time, "00:00:05,500")
        self.assertEqual(second_subtitle.end_time, "00:00:08,000")
        self.assertEqual(second_subtitle.text, "Welcome to SRT parsing.")
        
        # 3つ目の字幕（複数行）の確認
        third_subtitle = subtitles[2]
        self.assertEqual(third_subtitle.index, 3)
        self.assertEqual(third_subtitle.text, "Multiple lines\nare supported\nin subtitles.")
        
        # 4つ目の字幕（日本語）の確認
        fourth_subtitle = subtitles[3]
        self.assertEqual(fourth_subtitle.index, 4)
        self.assertEqual(fourth_subtitle.text, "日本語のテストです。\n漢字、ひらがな、カタカナが含まれます。")
    
    def test_save_srt_basic(self):
        """基本的なSRT保存のテスト"""
        # テスト用の字幕データを作成
        subtitles = [
            Subtitle(1, "00:00:01,000", "00:00:03,000", "Test subtitle 1"),
            Subtitle(2, "00:00:04,000", "00:00:06,000", "Test subtitle 2\nMultiple lines"),
        ]
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            self.parser.save_srt(subtitles, temp_path)
            
            # 保存したファイルを読み込んで確認
            with open(temp_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            expected_content = (
                "1\n00:00:01,000 --> 00:00:03,000\nTest subtitle 1\n\n"
                "2\n00:00:04,000 --> 00:00:06,000\nTest subtitle 2\nMultiple lines"
            )
            self.assertEqual(content, expected_content)
            
        finally:
            # 一時ファイルを削除
            os.unlink(temp_path)
    
    def test_roundtrip_conversion(self):
        """読み込み→保存→読み込みの往復変換テスト"""
        # 元のファイルを読み込み
        original_subtitles = self.parser.parse_srt(str(self.sample_srt))
        
        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            self.parser.save_srt(original_subtitles, temp_path)
            
            # 保存したファイルを再度読み込み
            reloaded_subtitles = self.parser.parse_srt(temp_path)
            
            # 元のデータと比較
            self.assertEqual(len(original_subtitles), len(reloaded_subtitles))
            
            for original, reloaded in zip(original_subtitles, reloaded_subtitles):
                self.assertEqual(original.index, reloaded.index)
                self.assertEqual(original.start_time, reloaded.start_time)
                self.assertEqual(original.end_time, reloaded.end_time)
                self.assertEqual(original.text, reloaded.text)
                
        finally:
            os.unlink(temp_path)
    
    def test_detect_encoding(self):
        """エンコーディング検出のテスト"""
        encoding = self.parser.detect_encoding(str(self.sample_srt))
        self.assertIn(encoding.lower(), ['utf-8', 'ascii'])
    
    def test_validate_time_format(self):
        """時刻形式検証のテスト"""
        # 正しい形式
        self.assertTrue(self.parser.validate_time_format("00:01:23,456"))
        self.assertTrue(self.parser.validate_time_format("12:34:56,789"))
        
        # 間違った形式
        self.assertFalse(self.parser.validate_time_format("1:23:45,678"))  # 時間が1桁
        self.assertFalse(self.parser.validate_time_format("00:01:23.456"))  # ピリオド
        self.assertFalse(self.parser.validate_time_format("00:01:23,45"))   # ミリ秒が2桁
        self.assertFalse(self.parser.validate_time_format("25:01:23,456"))  # 25時間
        self.assertFalse(self.parser.validate_time_format("00:61:23,456"))  # 61分
        self.assertFalse(self.parser.validate_time_format("00:01:61,456"))  # 61秒
    
    def test_format_time(self):
        """時刻フォーマットのテスト"""
        formatted = self.parser.format_time(1, 23, 45, 678)
        self.assertEqual(formatted, "01:23:45,678")
        
        formatted = self.parser.format_time(0, 0, 1, 0)
        self.assertEqual(formatted, "00:00:01,000")
    
    def test_empty_file(self):
        """空ファイルのテスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            subtitles = self.parser.parse_srt(temp_path)
            self.assertEqual(len(subtitles), 0)
        finally:
            os.unlink(temp_path)
    
    def test_malformed_srt(self):
        """不正な形式のSRTファイルのテスト"""
        malformed_content = """1
invalid_timestamp
Some subtitle text

2
00:00:05,000 --> 00:00:08,000
Valid subtitle
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(malformed_content)
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                self.parser.parse_srt(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_missing_index(self):
        """字幕番号が欠けているSRTファイルのテスト"""
        malformed_content = """not_a_number
00:00:01,000 --> 00:00:04,000
Some subtitle text
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False, encoding='utf-8') as f:
            f.write(malformed_content)
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                self.parser.parse_srt(temp_path)
        finally:
            os.unlink(temp_path)
    
    def test_file_not_found(self):
        """存在しないファイルのテスト"""
        with self.assertRaises(FileNotFoundError):
            self.parser.parse_srt("non_existent_file.srt")
        
        with self.assertRaises(FileNotFoundError):
            self.parser.detect_encoding("non_existent_file.srt")
    
    def test_save_empty_subtitles(self):
        """空の字幕リストの保存テスト"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                self.parser.save_srt([], temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_save_invalid_subtitle(self):
        """不正な字幕データの保存テスト"""
        invalid_subtitles = [
            Subtitle(1, "", "00:00:03,000", "Test")  # start_timeが空
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.srt', delete=False) as f:
            temp_path = f.name
        
        try:
            with self.assertRaises(ValueError):
                self.parser.save_srt(invalid_subtitles, temp_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()