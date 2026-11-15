"""AI ライティングツール（Streamlit + Gemini API）"""

import os
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv
from google.genai import errors

from gemini_client import FALLBACK_API_KEY, MAX_RETRIES, DEFAULT_MODELS, list_models, stream_generate
from tools import TOOLS, Field, Tool

load_dotenv()

st.set_page_config(page_title="AI ライティングツール", page_icon="✍️", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []  # 生成結果の履歴（新しいものが先頭）


@st.cache_data(ttl=3600, show_spinner=False)
def get_models(api_key: str) -> list[str]:
    """使えるモデルの一覧。取得できなければ DEFAULT_MODELS を返す。"""
    if not api_key:
        return DEFAULT_MODELS
    try:
        models = list_models(api_key)
    except Exception:
        return DEFAULT_MODELS
    return models or DEFAULT_MODELS


# ---------------------------------------------------------------------------
# サイドバー
# ---------------------------------------------------------------------------
with st.sidebar:
    st.title("✍️ AI ライティング")

    tool: Tool = st.radio(
        "ツールを選択",
        TOOLS,
        format_func=lambda t: f"{t.icon} {t.name}",
        label_visibility="collapsed",
    )

    st.divider()
    with st.expander("⚙️ 設定", expanded=not os.getenv("GEMINI_API_KEY")):
        api_key = st.text_input(
            "Gemini API キー",
            value=os.getenv("GEMINI_API_KEY", FALLBACK_API_KEY),
            type="password",
            help=".env ファイルに GEMINI_API_KEY を書いておくと自動で読み込まれます。",
        )
        models = get_models(api_key)
        default_model = DEFAULT_MODELS[0]
        model = st.selectbox(
            "モデル",
            models,
            index=models.index(default_model) if default_model in models else 0,
            help="API キーを入力すると、その時点で使えるモデルを自動で取得します。",
        )
        temperature = st.slider(
            "創造性（temperature）",
            0.0, 2.0, tool.temperature, 0.1,
            key=f"temperature_{tool.key}",
            help="低いほど正確・安定、高いほど自由で多様な文章になります。",
        )

    st.caption(f"履歴: {len(st.session_state.history)} 件")
    if st.session_state.history and st.button("履歴をクリア", use_container_width=True):
        st.session_state.history = []
        st.rerun()


# ---------------------------------------------------------------------------
# 入力フォーム
# ---------------------------------------------------------------------------
def render_field(f: Field, tool_key: str):
    key = f"{tool_key}_{f.key}"
    if f.kind == "textarea":
        return st.text_area(f.label, placeholder=f.placeholder, height=f.height, key=key)
    if f.kind == "select":
        index = f.options.index(f.default) if f.default in f.options else 0
        return st.selectbox(f.label, f.options, index=index, key=key)
    if f.kind == "number":
        return st.number_input(f.label, min_value=1, value=int(f.default), step=1, key=key)
    return st.text_input(f.label, placeholder=f.placeholder, key=key)


st.header(f"{tool.icon} {tool.name}")
st.caption(tool.description)

input_col, output_col = st.columns([1, 1], gap="large")

with input_col:
    with st.form(f"form_{tool.key}"):
        values = {f.key: render_field(f, tool.key) for f in tool.fields}
        submitted = st.form_submit_button("✨ 生成する", type="primary", use_container_width=True)


# ---------------------------------------------------------------------------
# 生成結果
# ---------------------------------------------------------------------------
ERROR_MESSAGES = {
    400: "リクエストが受け付けられませんでした。API キーが正しいか確認してください。",
    403: "この API キーではモデルを使う権限がありません。API キーを確認してください。",
    404: "選択中のモデルは使えません。サイドバーの「設定」で別のモデルを選んでください。",
    429: "利用回数の上限に達しました。しばらく待ってから、もう一度お試しください。",
    500: "Gemini 側でエラーが起きました。少し時間をおいて、もう一度お試しください。",
    503: "モデルが混み合っています。少し時間をおいてもう一度お試しいただくか、"
         "サイドバーの「設定」で別のモデルを選んでください。",
}


def show_error(e: Exception):
    """エラーの対処方法を日本語で表示し、元のエラー内容は折りたたんで見せる。"""
    message = ERROR_MESSAGES.get(e.code) if isinstance(e, errors.APIError) else None
    st.error(message or "生成中にエラーが発生しました。")
    with st.expander("エラーの詳細"):
        st.code(f"{e}\n(model={model}, api_key={api_key})", language=None, wrap_lines=True)


def render_result_actions(text: str, filename: str, key: str):
    """コピー用の表示とダウンロードボタン。"""
    with st.expander("📋 テキストをコピー"):
        st.code(text, language=None, wrap_lines=True)
    st.download_button(
        "💾 ダウンロード（.md）",
        text,
        file_name=filename,
        mime="text/markdown",
        key=key,
    )


with output_col:
    st.subheader("生成結果")

    if submitted:
        missing = [f.label for f in tool.fields if f.required and not str(values[f.key]).strip()]
        if not api_key:
            st.error("サイドバーの「設定」で Gemini API キーを入力してください。")
        elif missing:
            st.warning(f"次の項目を入力してください: {', '.join(missing)}")
        else:
            prompt = tool.build_prompt(values)
            retry_notice = st.empty()

            def notify_retry(attempt: int, e: errors.APIError):
                reason = "モデルが混み合っている" if e.code == 503 else f"一時的なエラー（{e.code}）の"
                retry_notice.info(f"{reason}ため、再試行しています（{attempt}/{MAX_RETRIES} 回目）…")

            try:
                with st.spinner(f"{model} で生成中…"), st.container(border=True):
                    result = st.write_stream(
                        stream_generate(api_key, model, tool.system, prompt, temperature, notify_retry)
                    )
            except Exception as e:
                retry_notice.empty()
                show_error(e)
            else:
                retry_notice.empty()
                timestamp = datetime.now()
                st.session_state.history.insert(0, {
                    "tool": tool.name,
                    "icon": tool.icon,
                    "time": timestamp.strftime("%Y-%m-%d %H:%M"),
                    "result": result,
                })
                render_result_actions(
                    result,
                    f"{tool.key}_{timestamp:%Y%m%d_%H%M%S}.md",
                    key="download_latest",
                )
    else:
        st.info("左のフォームに入力して「生成する」を押してください。")


# ---------------------------------------------------------------------------
# 履歴
# ---------------------------------------------------------------------------
past = st.session_state.history[1:] if submitted else st.session_state.history
if past:
    st.divider()
    st.subheader("🕘 履歴")
    for i, item in enumerate(past):
        with st.expander(f"{item['icon']} {item['tool']}（{item['time']}）"):
            st.markdown(item["result"], unsafe_allow_html=True)
            render_result_actions(item["result"], f"history_{i}.md", key=f"download_history_{i}")
