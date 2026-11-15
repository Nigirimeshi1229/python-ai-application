"""Streamlit + Gemini アプリの機械的なセキュリティ検査。

使い方:
    python scan.py <プロジェクトのフォルダ>

正規表現とファイルの有無だけで判定できる項目を調べ、Markdown で結果を出す。
見つけた秘密情報（API キーなど）は、先頭4文字以外を伏せ字にして表示する。
ここで見つからなかったからといって安全とは限らない。コードの流れを追う確認は
SKILL.md の手順どおり、人（Claude）が読んで行う。
"""

import re
import subprocess
import sys
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".agents", ".claude", "node_modules"}
TEXT_EXTS = {".py", ".toml", ".json", ".yaml", ".yml", ".md", ".txt", ".cfg", ".ini", ".example"}

# 秘密情報らしき文字列
SECRET_PATTERNS = [
    ("Google / Gemini API キー", re.compile(r"AIza[0-9A-Za-z_\-]{30,}")),
    ("OpenAI 形式の API キー", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("API キー・パスワードの直書き",
     re.compile(r"""(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*["'][^"'\s]{12,}["']""")),
]

# コード中の危険な書き方: (重要度, 見出し, 正規表現, 説明)
CODE_PATTERNS = [
    ("中", "HTML をそのまま表示", re.compile(r"unsafe_allow_html\s*=\s*True"),
     "生成結果や入力をそのまま HTML として表示すると、スクリプトが埋め込まれる恐れがある。"),
    ("中", "HTML をそのまま表示", re.compile(r"\bst\.html\(|components\.html\(|components\.v1\.html\("),
     "表示する中身に外部（生成結果・入力）の文字列が入っていないか確認する。"),
    ("高", "任意コード実行", re.compile(r"(?<![\w.])(eval|exec)\s*\("),
     "入力や生成結果が渡るとプログラムを乗っ取られる。"),
    ("高", "任意コード実行", re.compile(r"pickle\.loads?\(|yaml\.load\((?![^)]*SafeLoader)"),
     "信頼できないデータを読み込むとコードが実行される。"),
    ("高", "シェル実行", re.compile(r"os\.system\(|shell\s*=\s*True"),
     "文字列を組み立ててシェルに渡すとコマンドを注入される。"),
    ("中", "秘密情報の表示・出力",
     re.compile(r"(?i)(print|logging\.\w+|logger\.\w+|st\.(write|text|code|markdown|json))\s*\(.*(api_key|secret|token|password)"),
     "API キーなどが画面やログに出ていないか確認する。"),
    ("低", "環境変数の一括表示", re.compile(r"(st\.\w+|print)\s*\(\s*(dict\()?os\.environ"),
     "環境変数をまとめて表示すると API キーも一緒に表示される。"),
]


def mask(value: str) -> str:
    return value[:4] + "*" * 8 if len(value) > 4 else "****"


def iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS or part.endswith("-workspace") for part in path.relative_to(root).parts):
            continue
        if path.is_file() and (path.suffix in TEXT_EXTS or path.name.startswith(".env")):
            yield path


def read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def scan(root: Path) -> list[tuple[str, str, str, str]]:
    """(重要度, 見出し, 場所, 説明) のリストを返す。"""
    findings = []
    gitignore = read_lines(root / ".gitignore")
    ignored = {line.strip().rstrip("/") for line in gitignore if line.strip() and not line.startswith("#")}

    # 1. 秘密情報の直書き（.env 本体は「置き場所として正しい」ので対象外。代わりに 2 で管理を確認）
    for path in iter_files(root):
        rel = path.relative_to(root).as_posix()
        if path.name == ".env":
            continue
        for i, line in enumerate(read_lines(path), 1):
            for label, pat in SECRET_PATTERNS:
                m = pat.search(line)
                if m:
                    findings.append(("高", f"秘密情報の直書き（{label}）", f"{rel}:{i}",
                                     f"`{mask(m.group(0))}` のような値が書かれている。.env に移し、"
                                     "すでに共有・コミットした場合はキーを無効化して作り直す。"))

    # 2. .env と secrets.toml の管理
    for name in (".env", ".streamlit/secrets.toml"):
        if name not in ignored and f"/{name}" not in ignored:
            sev = "高" if (root / name).exists() else "中"
            findings.append((sev, "秘密ファイルが .gitignore に入っていない", ".gitignore",
                             f"`{name}` を .gitignore に追加する。"))
    if (root / ".git").exists():
        try:
            out = subprocess.run(["git", "-C", str(root), "ls-files", ".env", ".streamlit/secrets.toml"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            out = ""
        if out:
            findings.append(("高", "秘密ファイルが git に登録されている", out.replace("\n", ", "),
                             "`git rm --cached` で登録を外し、キーを無効化して作り直す。履歴にも残っている点に注意。"))

    # 3. Streamlit の公開設定
    config = root / ".streamlit" / "config.toml"
    for i, line in enumerate(read_lines(config), 1):
        s = line.split("#")[0].strip().replace(" ", "")
        if s.startswith("address=") and "localhost" not in s and "127.0.0.1" not in s:
            findings.append(("高", "社内ネットワークに公開される設定", f".streamlit/config.toml:{i}",
                             "`address = \"localhost\"` にする。認証が無いので、同じネットワークの人が API キーを使えてしまう。"))
        if s in ("enableXsrfProtection=false", "enableCORS=false"):
            findings.append(("中", "Streamlit の保護機能が無効", f".streamlit/config.toml:{i}",
                             "特別な理由がなければ true（既定値）に戻す。"))
    if not config.exists():
        findings.append(("情報", "公開範囲が起動コマンド頼み", ".streamlit/config.toml（無し）",
                         "`--server.address localhost` を付け忘れると社内に公開される。"
                         "config.toml に `[server] address = \"localhost\"` を書いておくと付け忘れを防げる。"))

    # 4. コード中の危険な書き方
    for path in iter_files(root):
        if path.suffix != ".py":
            continue
        rel = path.relative_to(root).as_posix()
        for i, line in enumerate(read_lines(path), 1):
            if line.lstrip().startswith("#"):
                continue
            for sev, label, pat, note in CODE_PATTERNS:
                if pat.search(line):
                    findings.append((sev, label, f"{rel}:{i}", f"{note} 該当行: `{line.strip()[:100]}`"))

    # 5. 依存パッケージのバージョン指定
    for i, line in enumerate(read_lines(root / "requirements.txt"), 1):
        s = line.split("#")[0].strip()
        if s and not any(op in s for op in ("==", "<", "~=")):
            findings.append(("情報", "依存パッケージの上限が無い", f"requirements.txt:{i}",
                             f"`{s}` はインストールのたびに最新版が入る。動作確認したバージョンに固定するかは好みで判断。"))

    return findings


ORDER = {"高": 0, "中": 1, "低": 2, "情報": 3}


def main():
    # Windows で出力をパイプに渡すと cp932 になり、「—」などで落ちるため UTF-8 に固定する
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    findings = sorted(scan(root), key=lambda f: ORDER[f[0]])
    print(f"# 機械チェックの結果（{root.name}）\n")
    if not findings:
        print("機械的に検出できる問題は見つかりませんでした。")
        return
    for sev, label, where, note in findings:
        print(f"- [{sev}] {label} — {where}\n  {note}")


if __name__ == "__main__":
    main()
