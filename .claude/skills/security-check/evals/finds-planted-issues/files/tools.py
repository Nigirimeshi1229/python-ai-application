"""ライティングツールの定義。

各ツールは「入力フォームの項目」と「プロンプトの組み立て方」を持つ。
新しいツールを追加したいときは、Tool を1つ作って TOOLS に追加するだけでよい。
"""

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Field:
    key: str
    label: str
    kind: str = "text"  # text / textarea / select / number
    options: list[str] = field(default_factory=list)
    default: str | int = ""
    placeholder: str = ""
    required: bool = False
    height: int = 200


@dataclass
class Tool:
    key: str
    icon: str
    name: str
    description: str
    system: str
    fields: list[Field]
    build_prompt: Callable[[dict], str]
    temperature: float = 0.7


def _optional(label: str, value: str) -> str:
    """値が入力されているときだけ「ラベル: 値」の行を返す。"""
    return f"{label}: {value}\n" if value else ""


TONES = ["丁寧・フォーマル", "ビジネス標準", "親しみやすい", "カジュアル", "熱意がある", "簡潔・事務的"]


# ---------------------------------------------------------------------------
# ブログ記事
# ---------------------------------------------------------------------------
def _blog_prompt(v: dict) -> str:
    return (
        "以下の条件でブログ記事を書いてください。\n\n"
        f"テーマ: {v['topic']}\n"
        + _optional("想定読者", v["audience"])
        + _optional("含めたいキーワード", v["keywords"])
        + f"文体: {v['tone']}\n"
        f"目安の文字数: 約{v['length']}文字\n"
        + _optional("補足・盛り込みたい内容", v["notes"])
        + "\n出力形式:\n"
        "- 最初に記事タイトル案を3つ提示\n"
        "- その後、Markdown の見出し（##, ###）を使った本文\n"
        "- 導入 → 本論 → まとめ の構成にする"
    )


BLOG = Tool(
    key="blog",
    icon="📝",
    name="ブログ記事作成",
    description="テーマを入力すると、見出し構成付きのブログ記事を執筆します。",
    system=(
        "あなたは経験豊富なプロのWebライターです。読者の関心を引き、"
        "最後まで読みたくなる、わかりやすく正確な日本語の記事を書きます。"
        "SEO を意識しつつも、自然で読みやすい文章を優先します。"
    ),
    fields=[
        Field("topic", "テーマ・タイトル", placeholder="例: 初心者向け Python の勉強方法", required=True),
        Field("audience", "想定読者", placeholder="例: プログラミング未経験の社会人"),
        Field("keywords", "含めたいキーワード（カンマ区切り）", placeholder="例: 独学, 無料, おすすめ"),
        Field("tone", "文体", kind="select", options=["です・ます調（丁寧）", "だ・である調", "カジュアル・会話調"]),
        Field("length", "文字数の目安", kind="number", default=2000),
        Field("notes", "補足・盛り込みたい内容", kind="textarea", height=100),
    ],
    build_prompt=_blog_prompt,
    temperature=0.8,
)


# ---------------------------------------------------------------------------
# メール返信
# ---------------------------------------------------------------------------
def _email_prompt(v: dict) -> str:
    return (
        "以下の受信メールに対する返信文を作成してください。\n\n"
        f"【受信メール】\n{v['received']}\n\n"
        f"【返信で伝えたいこと】\n{v['intent'] or '（内容に合わせて適切に返信）'}\n\n"
        f"相手との関係: {v['relation']}\n"
        f"トーン: {v['tone']}\n"
        + _optional("差出人（自分）の名前", v["my_name"])
        + "\n件名（Re: を含む）と本文を出力してください。"
        "返信のパターンを2案（標準的なもの・より簡潔なもの）提示してください。"
    )


EMAIL = Tool(
    key="email",
    icon="✉️",
    name="メール返信作成",
    description="受信したメールを貼り付けると、状況に合った返信文を考えます。",
    system=(
        "あなたはビジネスコミュニケーションの専門家です。"
        "相手との関係性に応じた適切な敬語を使い、要点が明確で失礼のない日本語のメールを作成します。"
    ),
    fields=[
        Field("received", "受信したメール本文", kind="textarea", required=True, height=220),
        Field("intent", "返信で伝えたいこと（箇条書きでOK）", kind="textarea", height=100,
              placeholder="例: 日程はOK / 資料は来週送る / 金曜は不在"),
        Field("relation", "相手との関係", kind="select",
              options=["社外（取引先・顧客）", "社内（上司）", "社内（同僚・部下）", "友人・知人"]),
        Field("tone", "トーン", kind="select", options=TONES),
        Field("my_name", "自分の名前（署名用）"),
    ],
    build_prompt=_email_prompt,
)


# ---------------------------------------------------------------------------
# 要約
# ---------------------------------------------------------------------------
def _summary_prompt(v: dict) -> str:
    return (
        f"以下の文章を「{v['style']}」の形式で要約してください。\n"
        f"長さの目安: {v['length']}\n\n"
        f"【文章】\n{v['text']}"
    )


SUMMARY = Tool(
    key="summary",
    icon="📄",
    name="文章要約",
    description="長い文章のポイントを、指定した形式・長さで要約します。",
    system=(
        "あなたは優秀な編集者です。文章の要点を正確に把握し、"
        "元の意味を損なわずに簡潔にまとめます。原文にない情報は付け加えません。"
    ),
    fields=[
        Field("text", "要約したい文章", kind="textarea", required=True, height=300),
        Field("style", "要約の形式", kind="select",
              options=["箇条書き", "文章（段落）", "3行まとめ", "一言（ひとこと）", "見出し＋要点"]),
        Field("length", "長さ", kind="select", options=["短め", "標準", "詳しめ"], default="標準"),
    ],
    build_prompt=_summary_prompt,
    temperature=0.3,
)


# ---------------------------------------------------------------------------
# 文章校正・推敲
# ---------------------------------------------------------------------------
def _proofread_prompt(v: dict) -> str:
    return (
        f"以下の文章を校正・推敲してください。重視する点: {v['focus']}\n\n"
        "出力形式:\n"
        "1. ## 修正後の文章\n"
        "2. ## 主な修正点（修正前 → 修正後 と理由を箇条書き）\n\n"
        f"【文章】\n{v['text']}"
    )


PROOFREAD = Tool(
    key="proofread",
    icon="🔍",
    name="文章校正・推敲",
    description="誤字脱字・文法ミスを直し、より読みやすい文章に整えます。",
    system=(
        "あなたは日本語の校正・校閲のプロです。誤字脱字、文法、表記ゆれ、"
        "冗長な表現を見つけ、書き手の意図を保ったまま読みやすく改善します。"
    ),
    fields=[
        Field("text", "校正したい文章", kind="textarea", required=True, height=300),
        Field("focus", "重視する点", kind="select",
              options=["誤字脱字・文法のみ（最小限の修正）", "読みやすさの改善", "ビジネス文書向けに整える", "簡潔にする"]),
    ],
    build_prompt=_proofread_prompt,
    temperature=0.3,
)


# ---------------------------------------------------------------------------
# 言い換え・トーン変換
# ---------------------------------------------------------------------------
def _rewrite_prompt(v: dict) -> str:
    return (
        f"以下の文章を「{v['tone']}」のトーンに書き換えてください。"
        f"意味は変えずに、書き換え案を{v['count']}パターン提示してください。\n\n"
        f"【文章】\n{v['text']}"
    )


REWRITE = Tool(
    key="rewrite",
    icon="🔄",
    name="言い換え・トーン変換",
    description="同じ内容を別の言い回しや、異なるトーンの文章に書き換えます。",
    system="あなたは表現力豊かな日本語のライターです。文章の意味を保ちながら、目的に合った言い回しに書き換えます。",
    fields=[
        Field("text", "書き換えたい文章", kind="textarea", required=True, height=200),
        Field("tone", "変換後のトーン", kind="select",
              options=TONES + ["やわらかく（角が立たないように）", "子どもにもわかるように", "専門的に"]),
        Field("count", "パターン数", kind="number", default=3),
    ],
    build_prompt=_rewrite_prompt,
    temperature=0.9,
)


# ---------------------------------------------------------------------------
# 翻訳
# ---------------------------------------------------------------------------
def _translate_prompt(v: dict) -> str:
    return (
        f"以下の文章を{v['target']}に翻訳してください。スタイル: {v['style']}\n"
        "翻訳文のあとに、訳し方に注意した箇所があれば簡単に補足してください。\n\n"
        f"【文章】\n{v['text']}"
    )


TRANSLATE = Tool(
    key="translate",
    icon="🌐",
    name="翻訳",
    description="文章を自然な表現で他の言語に翻訳します。",
    system="あなたはプロの翻訳者です。直訳ではなく、ネイティブが読んで自然に感じる訳文を作成します。",
    fields=[
        Field("text", "翻訳したい文章", kind="textarea", required=True, height=250),
        Field("target", "翻訳先の言語", kind="select",
              options=["英語", "日本語", "中国語（簡体字）", "韓国語", "スペイン語", "フランス語", "ドイツ語"]),
        Field("style", "スタイル", kind="select", options=["自然な訳", "ビジネス向け", "カジュアル", "直訳寄り"]),
    ],
    build_prompt=_translate_prompt,
    temperature=0.3,
)


# ---------------------------------------------------------------------------
# SNS 投稿
# ---------------------------------------------------------------------------
def _sns_prompt(v: dict) -> str:
    return (
        f"{v['platform']}向けの投稿文を{v['count']}パターン作成してください。\n\n"
        f"内容・伝えたいこと: {v['content']}\n"
        f"トーン: {v['tone']}\n"
        f"ハッシュタグ: {'付ける' if v['hashtag'] == 'あり' else '付けない'}\n"
        "各プラットフォームの文字数制限や文化に合わせてください。"
    )


SNS = Tool(
    key="sns",
    icon="📱",
    name="SNS投稿作成",
    description="X・Instagram などの SNS 向け投稿文を作成します。",
    system="あなたは SNS マーケティングに詳しいコピーライターです。拡散されやすく、共感を呼ぶ投稿文を作ります。",
    fields=[
        Field("content", "投稿したい内容", kind="textarea", required=True, height=150),
        Field("platform", "プラットフォーム", kind="select",
              options=["X（旧Twitter）", "Instagram", "Facebook", "LinkedIn", "Threads"]),
        Field("tone", "トーン", kind="select", options=["親しみやすい", "カジュアル", "熱意がある", "丁寧・フォーマル"]),
        Field("hashtag", "ハッシュタグ", kind="select", options=["あり", "なし"]),
        Field("count", "パターン数", kind="number", default=3),
    ],
    build_prompt=_sns_prompt,
    temperature=0.9,
)


# ---------------------------------------------------------------------------
# タイトル・キャッチコピー
# ---------------------------------------------------------------------------
def _catchcopy_prompt(v: dict) -> str:
    return (
        f"以下の対象について「{v['kind']}」の案を{v['count']}個考えてください。\n"
        "それぞれに狙い（どんな効果を狙ったか）を一言添えてください。\n\n"
        f"対象・内容: {v['subject']}\n"
        + _optional("ターゲット", v["target"])
        + _optional("イメージ・キーワード", v["keywords"])
    )


CATCHCOPY = Tool(
    key="catchcopy",
    icon="💡",
    name="タイトル・キャッチコピー",
    description="記事タイトル、商品のキャッチコピー、メール件名などのアイデアを出します。",
    system="あなたは一流のコピーライターです。短い言葉で人の心を動かす、印象に残るフレーズを生み出します。",
    fields=[
        Field("subject", "対象（商品・記事・イベントなど）", kind="textarea", required=True, height=120),
        Field("kind", "種類", kind="select",
              options=["キャッチコピー", "記事タイトル", "メール件名", "商品名・サービス名", "スローガン"]),
        Field("target", "ターゲット", placeholder="例: 30代の働く女性"),
        Field("keywords", "イメージ・キーワード", placeholder="例: 手軽, 本格的, 時短"),
        Field("count", "案の数", kind="number", default=10),
    ],
    build_prompt=_catchcopy_prompt,
    temperature=1.0,
)


# ---------------------------------------------------------------------------
# 議事録・メモ整理
# ---------------------------------------------------------------------------
def _minutes_prompt(v: dict) -> str:
    return (
        f"以下のメモを「{v['format']}」として整理してください。\n"
        "内容が不明な箇所は推測で埋めず「（要確認）」と記載してください。\n\n"
        f"【メモ】\n{v['memo']}"
    )


MINUTES = Tool(
    key="minutes",
    icon="🗒️",
    name="議事録・メモ整理",
    description="走り書きのメモや文字起こしを、整った議事録や文書にまとめます。",
    system="あなたは優秀な秘書です。断片的な情報を整理し、誰が読んでもわかる構造化された文書にまとめます。",
    fields=[
        Field("memo", "メモ・文字起こし", kind="textarea", required=True, height=300),
        Field("format", "整理の形式", kind="select",
              options=["議事録（日時・参加者・議題・決定事項・TODO）", "TODOリスト", "報告書", "要点メモ"]),
    ],
    build_prompt=_minutes_prompt,
    temperature=0.3,
)


# ---------------------------------------------------------------------------
# 自由入力
# ---------------------------------------------------------------------------
FREE = Tool(
    key="free",
    icon="✨",
    name="自由入力",
    description="上記にない文章作成の依頼を、自由にお願いできます。",
    system="あなたは何でも書ける優秀なライティングアシスタントです。依頼の意図を汲み取り、高品質な日本語の文章を作成します。",
    fields=[
        Field("request", "依頼内容", kind="textarea", required=True, height=250,
              placeholder="例: 退職する同僚へのメッセージを3パターン書いて"),
    ],
    build_prompt=lambda v: v["request"],
)


TOOLS: list[Tool] = [BLOG, EMAIL, SUMMARY, PROOFREAD, REWRITE, TRANSLATE, SNS, CATCHCOPY, MINUTES, FREE]
