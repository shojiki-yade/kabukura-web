#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""株クラ朝刊 公開・配信スクリプト
- news_collector_v2.py が生成済みのHTMLをGitHubにcommit/push
- index.html を最新日付にリダイレクト更新
- LINEグループに最新URLを送信

前提: news_collector_v2.py が REPO_ROOT/{YYYYMMDD}.html を生成済み
"""

import os
import sys
import io
import glob
import subprocess
import datetime

import requests

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

# =====================================================
# 設定
# =====================================================
GITHUB_USER = "shojiki-yade"
GITHUB_REPO = "kabukura-web"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_PAGES_BASE = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}"

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
LINE_GROUP_ID = os.environ.get("LINE_GROUP_ID", "")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.environ.get("REPO_DIR") or os.path.dirname(SCRIPT_DIR)


def find_latest_html(repo_root):
    """REPO_ROOT 直下の YYYYMMDD.html をスキャンして最新日付を返す"""
    pattern = os.path.join(repo_root, "????????.html")
    files = glob.glob(pattern)
    dates = []
    for f in files:
        name = os.path.basename(f).replace(".html", "")
        if name.isdigit() and len(name) == 8:
            dates.append(name)
    if not dates:
        return None
    return sorted(dates, reverse=True)[0]


def update_index(repo_root, latest_date):
    """index.html を最新日付HTMLへのリダイレクトで上書き"""
    index_html = (
        '<!DOCTYPE html>\n'
        '<html><head><meta charset="UTF-8">\n'
        f'<meta http-equiv="refresh" content="0; url={latest_date}.html">\n'
        '<title>株クラ朝刊</title></head>\n'
        f'<body><a href="{latest_date}.html">最新の朝刊はこちら</a></body></html>\n'
    )
    with open(os.path.join(repo_root, "index.html"), "w", encoding="utf-8") as f:
        f.write(index_html)
    print(f"[OK] index.html を {latest_date}.html にリダイレクト設定")


def git_push(repo_root, date_file):
    if not GITHUB_TOKEN:
        print("[SKIP] GITHUB_TOKEN 未設定のためプッシュをスキップ")
        return False

    remote_url = f"https://{GITHUB_USER}:{GITHUB_TOKEN}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"

    try:
        subprocess.run(["git", "-C", repo_root, "add", "."], check=True)
        commit = subprocess.run(
            ["git", "-C", repo_root, "commit", "-m", f"朝刊更新: {date_file}"],
            capture_output=True, text=True
        )
        if "nothing to commit" in (commit.stdout + commit.stderr):
            print("[INFO] 変更なし。プッシュスキップ")
            return True
        push = subprocess.run(
            ["git", "-C", repo_root, "push", remote_url, "HEAD:main"],
            capture_output=True, text=True, timeout=60
        )
        if push.returncode == 0:
            print(f"[OK] git push 完了")
            return True
        else:
            print(f"[ERROR] push 失敗: {push.stderr}")
            return False
    except Exception as e:
        print(f"[ERROR] git エラー: {e}")
        return False


def send_line(date_str, page_url):
    if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_GROUP_ID:
        print("[SKIP] LINE_CHANNEL_ACCESS_TOKEN または LINE_GROUP_ID 未設定")
        return False

    full_message = (
        f"📊 株クラ朝刊 {date_str}\n"
        f"👇 タップして確認\n"
        f"{page_url}"
    )
    api_url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {"to": LINE_GROUP_ID, "messages": [{"type": "text", "text": full_message}]}
    try:
        res = requests.post(api_url, headers=headers, json=data, timeout=30)
        if res.status_code == 200:
            print(f"[OK] LINE送信成功: {page_url}")
            return True
        else:
            print(f"[ERROR] LINE送信失敗: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"[ERROR] LINE送信エラー: {e}")
        return False


def main():
    latest_date = find_latest_html(REPO_ROOT)
    if not latest_date:
        print(f"[ERROR] HTMLファイルが見つかりません: {REPO_ROOT}")
        sys.exit(1)
    print(f"[INFO] 最新日付: {latest_date}")

    update_index(REPO_ROOT, latest_date)

    pushed = git_push(REPO_ROOT, latest_date)

    page_url = f"{GITHUB_PAGES_BASE}/{latest_date}.html"
    weekday_ja = "月火水木金土日"
    try:
        d = datetime.datetime.strptime(latest_date, "%Y%m%d")
        date_str = d.strftime("%Y年%m月%d日") + f"（{weekday_ja[d.weekday()]}）"
    except Exception:
        date_str = latest_date

    if pushed:
        send_line(date_str, page_url)
    else:
        print("[WARN] プッシュ失敗のためLINE送信スキップ")


if __name__ == "__main__":
    main()
