# Translate SRT MCP Server

SRT字幕ファイルを日本語に翻訳するMCPサーバーです。LM Studio などのローカルLLMサーバーと連携して、英語字幕を自然な日本語に翻訳します。

## 特徴

- 📝 SRT形式の字幕ファイルを解析・翻訳
- 🤖 LM Studio（OpenAI互換API）と連携
- 📤 翻訳結果はSRT形式のテキストデータとして返却

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

## 使用方法

### 1. LM Studio の準備

1. [LM Studio](https://lmstudio.ai/) をインストール
2. 翻訳用のモデルをダウンロード（例：Llama 3, Command-R+ など）
3. LM Studio のサーバーを起動（デフォルト: `http://localhost:1234/v1`）

### 2. MCP クライアント設定

MCPクライアント（Claude Desktop、Continue など）の設定ファイルに以下を追加します。
LM StudioのURLとモデル名は環境変数として設定します。

#### 推奨: uvx を使用（最も簡単）

GitHubリポジトリから直接起動（インストール不要）:

```json
{
  "mcpServers": {
    "translate-srt": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/sumik5/translate-srt-mcp",
        "translate-srt-mcp"
      ],
      "env": {
        "LM_STUDIO_URL": "http://localhost:1234",
        "LM_MODEL_NAME": "grapevine-AI/plamo-2-translate-gguf",
        "CHUNK_SIZE": "1000"
      }
    }
  }
}
```

#### ローカルインストール版を使用する場合

##### Claude Desktop の場合 (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS)

```json
{
  "mcpServers": {
    "translate-srt": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/path/to/translate-srt-mcp/server.py"
      ],
      "env": {
        "LM_STUDIO_URL": "http://localhost:1234/v1",
        "LM_MODEL_NAME": "llama-3-8b-instruct"
      }
    }
  }
}
```

#### 環境変数の説明

| 環境変数 | 説明 | デフォルト値 | 例 |
|---------|------|-------------|-----|
| `LM_STUDIO_URL` | LM StudioのAPI エンドポイントURL | `http://localhost:1234/v1` | `http://localhost:1234/v1` |
| `LM_MODEL_NAME` | 使用する翻訳モデルの名前（必須） | なし | `llama-3-8b-instruct`, `plamo-2-translate` など |
| `CHUNK_SIZE` | 一度に送信する最大文字数 | `1000` | `500`, `2000` など |

**注意事項：**
- `LM_MODEL_NAME` は必須です。設定されていない場合、エラーになります
- `CHUNK_SIZE` はSRT字幕ブロックを分割しないように設計されています（字幕の途中で切れることはありません）
- トークン数が多いモデルの場合は`CHUNK_SIZE`を大きく、少ないモデルの場合は小さく設定してください
- モデル名は LM Studio で実際に読み込んでいるモデルの名前と一致させてください

## トラブルシューティング

### LM Studio に接続できない場合

1. LM Studio サーバーが起動しているか確認
2. URL が正しいか確認（デフォルト: `http://localhost:1234/v1`）
3. ファイアウォールの設定を確認

### 翻訳が遅い場合

1. より高速なモデルを使用
2. LM Studio の設定でコンテキスト長を調整
3. バッチサイズを調整（`modules/translator.py`）

### 文字化けする場合

1. SRTファイルのエンコーディングを確認（UTF-8推奨）
2. 出力先のアプリケーションがUTF-8に対応しているか確認

## ライセンス

MIT License

## 貢献

プルリクエストを歓迎します。大きな変更の場合は、まずissueを開いて変更内容を議論してください。

## サポート

問題が発生した場合は、GitHubのIssueページで報告してください。
