# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

個人用の AI ライティングツール（ブログ記事、メール返信、要約、校正、翻訳など）。Python・Streamlit・Gemini API（`google-genai` SDK）で作っている。利用者は1人だけで、データベースも認証も使わない。この方針は今後も変えない。画面の文字、プロンプト、ユーザーへのメッセージはすべて日本語にする。

## コマンド

Windows / PowerShell で、プロジェクト内の仮想環境 `.venv` を使う。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py                                   # http://localhost:8501
.\.venv\Scripts\streamlit run app.py --server.address localhost        # 社内ネットワークに公開しない
```

API キーは python-dotenv で `.env` の `GEMINI_API_KEY` から読み込む（`.env.example` を参照）。サイドバーの「設定」から入力することもできる。

テストやリンターの仕組みはまだない。API を呼ばずに動作確認するときは、`streamlit.testing.v1.AppTest` で `app.py` を実行する。このとき `GEMINI_API_KEY` は空にし、プロジェクトのフォルダを `PYTHONPATH` に入れておく。`at.sidebar.radio[0].set_value(tool)` でツールを切り替え、`at.button[0]` をクリックして、`not at.exception`（エラーが起きていないこと）を確認する。

## 全体の仕組み

ツールの中身はすべて設定データとして定義している。`app.py` には、個別のツールに関するコードを書かない。

- `tools.py` — ツール1つを `Tool` データクラス1つで表す。持っている情報は、`system`（システム指示）、`Field` のリスト（入力欄。`kind` は `text` / `textarea` / `select` / `number` のどれか）、`build_prompt(values: dict) -> str`（プロンプトを組み立てる関数）、temperature の初期値。サイドバーには `TOOLS` リストの順に並ぶ。**ツールを追加するときは、`Tool` を定義して `TOOLS` に足すだけでよく、他のファイルは変更しなくてよい。** `build_prompt` に渡される `values` は、`Field.key` をキーにした辞書。空欄でもよい入力欄は `_optional()` を使って書く。
- `app.py` — サイドバーに、ツール選択・API キー・モデル・temperature のスライダーを表示する。スライダーの値はツールごとに保持する。`tool.fields` をもとに入力フォームを自動で作る。各入力欄のキーは `f"{tool.key}_{field.key}"` なので、ツールを切り替えても入力内容が残る。送信時に `required` の入力欄が埋まっているかを確認し、`st.write_stream` で結果を少しずつ表示する。結果は新しいものから順に `st.session_state.history` に入れる。履歴はブラウザのセッションの間しか残らない。
- `gemini_client.py` — `stream_generate()` が `client.models.generate_content_stream` を呼び出す。そのとき `system_instruction` と `temperature` を渡す。`list_models()` は、API キーで使える文章生成用の Gemini モデルを取得する。サイドバーのモデルの選択肢は、この一覧から作る（`app.py` の `get_models()` が1時間キャッシュする）。一覧を取得できないときは `DEFAULT_MODELS` を使う。`DEFAULT_MODELS` の先頭は初期値でもある。

## ツール・プロンプトを追加するときの決まりごと

- `system` には「あなたは〇〇の専門家です」という形で役割を書き、品質の基準（正確さ、読みやすさ、原文にない情報を足さない、など）を1〜2文で添える。
- `build_prompt` では、**出力の形を必ず指定する**（見出しの構成、箇条書き、案の数など）。結果は `st.markdown` で表示されるので、Markdown の見出しや箇条書きを使ってよい。
- 案をいくつか出させるツールでは、案の数を `number` の入力欄にしてユーザーが選べるようにする。
- temperature の初期値は、用途に合わせて次の目安で決める。
  - 正確さが大事な要約・校正・翻訳・議事録：0.3
  - 一般的な文章：0.7
  - アイデアを広げたい言い換え・SNS・キャッチコピー：0.9〜1.0
- 議事録のような、情報を整理するツールでは「わからない箇所は推測で埋めず（要確認）と書く」とプロンプトで指示する。

## 注意点

- `kind="number"` の入力欄は、`app.py` で `int(f.default)` として扱う。そのため `default` には必ず数値を入れる。空文字のままだとエラーになる。
- `kind="select"` の `default` は、`options` の中にある値にする。ない値を書いても、エラーにはならず先頭の選択肢が選ばれるので、間違いに気づきにくい。
- 入力欄は `st.form` の中にあるので、「生成する」を押すまで画面は再実行されない。入力に応じて表示を変えたい場合は、フォームの外に置く必要がある（temperature のスライダーがフォームの外にあるのはこのため）。
- エラーの扱いは2か所に分けている。
  - `gemini_client.py`：一時的なエラー（`RETRYABLE_CODES` に入っている 429・500・503）だけを、1秒・2秒・4秒と間隔を空けて最大 `MAX_RETRIES` 回やり直す。文章を返し始めた後はやり直さない（同じ文章が二重に表示されるため）。やり直すたびに `on_retry` を呼ぶので、`app.py` はそれを使って「再試行しています（n/3 回目）」と表示する。応答が `TIMEOUT_MS`（2分）途切れたらエラーにする。
  - `app.py`：`show_error()` が、エラーコードごとの対処方法を `ERROR_MESSAGES` から日本語で表示する。元のエラー内容は折りたたみの中に出す。
- モデル名は Gemini 側で変わったり廃止されたりする。実際に `gemini-2.5-flash` は 404 エラーになり、使えなくなった。モデルの選択肢は API から自動で取得しているので、直す必要があるのは初期値の `DEFAULT_MODELS` だけ。

## 作業の進め方

- ユーザーへの確認・質問・報告は日本語で行う。
- コードを変更したら、上の「コマンド」に書いた AppTest の方法で全ツールの画面がエラーなく表示されることを確認する。Gemini API を実際に呼ぶ確認は、利用料がかかるのでユーザーに頼まれたときだけ行う。
- アプリを起動するときは `--server.address localhost` を付け、社内ネットワークから開けないようにする（他の人に API キーを使われないため）。
- 新しいパッケージを追加したら `requirements.txt` にも書く。
- 機能を追加・変更したら、`README.md` の機能一覧も合わせて更新する。
