# ✍️ AI ライティングツール

Python + Streamlit + Gemini API で作った、個人用の AI ライティングツールです。

## 機能

| ツール | 内容 |
|---|---|
| 📝 ブログ記事作成 | テーマ・読者・キーワードから見出し付きの記事を執筆 |
| ✉️ メール返信作成 | 受信メールを貼り付けて、関係性・トーンに合った返信を2案作成 |
| 📄 文章要約 | 箇条書き・3行まとめなど形式を選んで要約 |
| 🔍 文章校正・推敲 | 誤字脱字・文法を修正し、修正点を一覧表示 |
| 🔄 言い換え・トーン変換 | 意味を保ったまま別のトーンに書き換え |
| 🌐 翻訳 | 自然な表現で多言語に翻訳 |
| 📱 SNS投稿作成 | X / Instagram などに合わせた投稿文 |
| 💡 タイトル・キャッチコピー | タイトル・コピー・件名のアイデア出し |
| 🗒️ 議事録・メモ整理 | メモや文字起こしを議事録・TODO に整理 |
| ✨ 自由入力 | 上記以外の自由な依頼 |

共通機能: ストリーミング表示 / コピー / Markdown ダウンロード / 生成履歴（ブラウザを閉じると消えます）

## セットアップ

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env   # .env を開いて GEMINI_API_KEY を設定
streamlit run app.py --server.address localhost
```

`--server.address localhost` は、社内ネットワークの他の PC から開けないようにする設定です（`.streamlit/config.toml` にも同じ設定があります）。

API キーは [Google AI Studio](https://aistudio.google.com/apikey) で取得できます。
`.env` を使わず、画面のサイドバー「設定」から入力することもできます。

## ファイル構成

- `app.py` … 画面（Streamlit）
- `tools.py` … 各ツールの入力項目とプロンプト定義
- `gemini_client.py` … Gemini API 呼び出し
- `.streamlit/config.toml` … Streamlit の設定（localhost でだけ開けるようにする）

## ツールを追加するには

`tools.py` で `Tool(...)` を1つ定義し、末尾の `TOOLS` リストに追加するだけで画面に反映されます。
