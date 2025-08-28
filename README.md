# translate-srt-mcp

SRT字幕ファイルを日本語に翻訳するMCPサーバー。LM Studioの翻訳モデルを使用して高品質な字幕翻訳を提供します。

## 主な機能

- **SRT形式の完全サポート**: タイムスタンプを保持したまま翻訳
- **チャンクベース処理**: 大きなファイルも効率的に処理
- **LM Studio統合**: ローカルLLMを使用した高品質な翻訳
- **エラーハンドリング**: 翻訳失敗時の自動リトライと詳細なエラー報告
- **統計情報**: 翻訳履歴と使用状況の追跡
- **分析ツール**: SRTファイルの検証と詳細分析
- **接続診断**: LM Studioの状態確認機能

## 利用可能なツール

### 1. translate_srt
字幕を日本語に翻訳します。

```python
# 基本的な使用法
translated = mcp__translate-srt__translate_srt(
    srt_content=content
)

# カスタム設定
translated = mcp__translate-srt__translate_srt(
    srt_content=content,
    model_name="llama-3.2-3b",
    chunk_size=500,
    preserve_formatting=True
)
```

### 2. analyze_srt
SRTファイルの統計情報を分析します。

```python
stats = mcp__translate-srt__analyze_srt(
    srt_content=content,
    detailed=True  # 詳細な分析を含む
)
```

### 3. check_lm_studio_status
LM Studioの接続状態を確認します。

```python
status = mcp__translate-srt__check_lm_studio_status(
    lm_studio_url="http://localhost:1234",
    model_name="llama-3.2-3b"
)
```

### 4. preview_srt
字幕のプレビューを生成します。

```python
preview = mcp__translate-srt__preview_srt(
    srt_content=content,
    num_entries=5,
    show_start=True,
    show_end=True
)
```

### 5. get_server_info
サーバー情報と統計を取得します。

```python
info = mcp__translate-srt__get_server_info()
```

## 使用例

### MCPクライアントでの実際の使用手順

```python
# 1. LM Studioの状態を確認
status = await check_lm_studio_status()
if not status["api_reachable"]:
    print("LM Studioが起動していません")
    
# 2. SRTファイルを読み込み
srt_content = read_file("movie.srt")

# 3. 分析して内容を確認
analysis = await analyze_srt(srt_content, detailed=True)
print(f"字幕数: {analysis['subtitle_count']}")
print(f"総時間: {analysis['duration_formatted']}")

# 4. プレビュー表示
preview = await preview_srt(srt_content, num_entries=3)
print("最初の3つの字幕:")
for entry in preview["preview_entries"]["start"]:
    print(f"{entry['time']}: {entry['text']}")

# 5. 翻訳実行
translated = await translate_srt(
    srt_content=srt_content,
    model_name="llama-3.2-3b-instruct",
    chunk_size=1000
)

# 6. 結果を保存
write_file("movie_ja.srt", translated)

# 7. 統計情報を確認
info = await get_server_info()
print(f"翻訳回数: {info['statistics']['total_translations']}")
print(f"処理文字数: {info['statistics']['total_characters']}")
```

## 必要要件

- Python 3.13以上
- LM Studio または OpenAI互換APIサーバー
- uv パッケージマネージャー（推奨）

## インストール

### 方法1: uvx を使用（推奨・最も簡単）

インストール不要！mcp.jsonの設定だけで使用できます。

```bash
# テスト実行したい場合
uvx --from git+https://github.com/sumik5/translate-srt-mcp translate-srt-mcp

# 環境変数を設定して実行
LM_STUDIO_URL="http://localhost:1234" \
LM_MODEL_NAME="grapevine-AI/plamo-2-translate-gguf" \
uvx --from git+https://github.com/sumik5/translate-srt-mcp translate-srt-mcp
```

### 方法2: ローカルインストール

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/translate-srt-mcp.git
cd translate-srt-mcp

# 依存関係をインストール（uvを使用）
uv sync

# または pip を使用
pip install -r requirements.txt
```

## 環境変数

```bash
# LM StudioのAPI URL (デフォルト: http://localhost:1234/v1)
export LM_STUDIO_URL="http://localhost:1234"

# 使用する翻訳モデル名 (必須)
export LM_MODEL_NAME="llama-3.2-3b-instruct"

# デフォルトのチャンクサイズ (デフォルト: 1000)
export CHUNK_SIZE="1000"
```

## Claude Codeでの設定例

To use this server with the Claude Desktop app, add the following configuration to the "MCP Servers" section of your Claude settings:

```json
"mcpServers": {
  "translate-srt": {
    "command": "uv",
    "args": [
      "--directory",
      "/path/to/translate-srt-mcp",
      "run",
      "translate-srt-mcp"
    ],
    "env": {
      "LM_STUDIO_URL": "http://localhost:1234",
      "LM_MODEL_NAME": "llama-3.2-3b-instruct",
      "CHUNK_SIZE": "1000"
    }
  }
}
```

## MCPクライアントでの使用時のベストプラクティス

1. **使用前の準備**
   - LM Studioを起動し、適切なモデルをロード
   - `check_lm_studio_status`で接続確認

2. **大きなファイルの処理**
   - `analyze_srt`で事前にファイルサイズを確認
   - 適切な`chunk_size`を設定（500-2000を推奨）

3. **エラー対処**
   - 接続エラー: LM Studioの起動状態を確認
   - モデルエラー: 正しいモデル名を指定
   - 翻訳エラー: チャンクサイズを調整

4. **品質向上のヒント**
   - 専門用語が多い場合は小さいチャンクサイズを使用
   - `preserve_formatting=True`で元の改行を保持
   - 翻訳後に`preview_srt`で結果を確認

## Development

Install dependencies:
```bash
uv install
```

For development with auto-reloading:
```bash
uv run fastmcp dev translate_srt_mcp.main:mcp
```

## トラブルシューティング

### LM Studioに接続できない
```python
# 接続状態を確認
status = await check_lm_studio_status()
print(status["recommendation"])
```

### モデルが見つからない
```python
# 利用可能なモデルを確認
status = await check_lm_studio_status()
print("利用可能なモデル:", status["available_models"])
```

### 翻訳が途中で止まる
- チャンクサイズを小さくする（例: 500）
- タイムアウト時間を増やす（translator.pyで設定）

## ライセンス

MIT License