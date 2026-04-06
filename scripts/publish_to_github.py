#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
株クラ朝刊 GitHub Pages 公開スクリプト
- Markdownレポートを静的HTMLに変換
- kabukura-web リポジトリにgit push
- GitHub Pages で固定URLを公開
- LINEにURLを送信

URL形式: https://shojiki-yade.github.io/kabukura-web/YYYYMMDD.html
"""

import os
import re
import glob
import subprocess
import datetime
import requests

# =====================================================
# 設定
# =====================================================
GITHUB_USER = "shojiki-yade"
GITHUB_REPO = "kabukura-web"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_PAGES_BASE = f"https://{GITHUB_USER}.github.io/{GITHUB_REPO}"

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get(
    "LINE_CHANNEL_ACCESS_TOKEN",
    "hf+HsyL6s3roeP1QKflE3RDiPwuQBxQSMb51uALi4oGHeGG/aqcxRy2rXXsZORgvwvG31wkEFIEB1XepTfx/dCTEJRBoJQpLlmsJHkL1Uc5qT1HmFY8fdkmWgJLbAQ5swH4vU2DoOrjkIimGlPhYhgdB04t89/1O/w1cDnyilFU="
)
LINE_GROUP_ID = os.environ.get("LINE_GROUP_ID", "C4f779e049966034f8bdf83b08139cf2c")

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
REPO_DIR = os.environ.get("REPO_DIR", "/home/ubuntu/kabukura_web")

# =====================================================
# HTML テンプレート（manus.im風 白背景シンプルデザイン）
# =====================================================
HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<title>📊 株クラ朝刊 {date}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #ffffff;
    color: #1a1a1a;
    font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', sans-serif;
    line-height: 1.75;
    font-size: 15px;
  }}
  .page-header {{
    border-bottom: 1px solid #e5e7eb;
    padding: 28px 24px 20px;
    max-width: 780px;
    margin: 0 auto;
  }}
  .page-header h1 {{
    font-size: 1.6rem;
    font-weight: 700;
    color: #111;
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .page-header .meta {{
    margin-top: 6px;
    font-size: 0.82rem;
    color: #6b7280;
  }}
  .page-header .desc {{
    margin-top: 4px;
    font-size: 0.88rem;
    color: #374151;
  }}
  .container {{
    max-width: 780px;
    margin: 0 auto;
    padding: 24px 24px 80px;
  }}
  .date-nav {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 28px;
    padding-bottom: 16px;
    border-bottom: 1px solid #e5e7eb;
  }}
  .date-nav a {{
    background: #f3f4f6;
    border: 1px solid #e5e7eb;
    color: #374151;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    text-decoration: none;
    transition: all 0.15s;
  }}
  .date-nav a.active {{
    background: #e94560;
    border-color: #e94560;
    color: #fff;
    font-weight: 600;
  }}
  .date-nav a:hover:not(.active) {{
    background: #e5e7eb;
  }}
  /* トレンドセクション */
  .trends-section {{
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #e94560;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 32px;
  }}
  .trends-section h2 {{
    font-size: 0.95rem;
    font-weight: 700;
    color: #e94560;
    margin-bottom: 12px;
  }}
  .trend-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }}
  .trend-tag {{
    background: #fff;
    border: 1px solid #d1d5db;
    border-radius: 20px;
    padding: 3px 12px;
    font-size: 0.8rem;
    color: #374151;
    text-decoration: none;
    transition: all 0.15s;
  }}
  .trend-tag:hover {{ background: #e94560; border-color: #e94560; color: #fff; }}
  .trend-tag .traffic {{ color: #f5a623; font-size: 0.72rem; margin-left: 4px; }}
  /* ニュースカード */
  .news-card {{
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 20px 22px;
    margin-bottom: 20px;
    transition: box-shadow 0.15s;
    background: #fff;
  }}
  .news-card:hover {{ box-shadow: 0 4px 16px rgba(0,0,0,0.08); }}
  .card-header {{
    display: flex;
    align-items: flex-start;
    gap: 14px;
    margin-bottom: 12px;
  }}
  .rank {{
    background: #e94560;
    color: #fff;
    font-size: 0.9rem;
    font-weight: 700;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }}
  .rank.gold {{ background: #f5a623; }}
  .rank.silver {{ background: #9ca3af; }}
  .rank.bronze {{ background: #cd7f32; }}
  .card-title {{ flex: 1; }}
  .category-badge {{
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 10px;
    border-radius: 20px;
    margin-bottom: 5px;
    font-weight: 600;
    background: #fee2e2;
    color: #dc2626;
    border: 1px solid #fca5a5;
  }}
  .cat-tax {{ background: #fee2e2; color: #dc2626; border-color: #fca5a5; }}
  .cat-work {{ background: #dcfce7; color: #16a34a; border-color: #86efac; }}
  .cat-price {{ background: #dbeafe; color: #2563eb; border-color: #93c5fd; }}
  .cat-salary {{ background: #fef9c3; color: #ca8a04; border-color: #fde047; }}
  .cat-nisa {{ background: #cffafe; color: #0891b2; border-color: #67e8f9; }}
  .cat-market {{ background: #f3e8ff; color: #9333ea; border-color: #d8b4fe; }}
  .cat-macro {{ background: #ffedd5; color: #ea580c; border-color: #fdba74; }}
  .cat-z {{ background: #e0e7ff; color: #4338ca; border-color: #a5b4fc; }}
  .cat-default {{ background: #f3f4f6; color: #6b7280; border-color: #d1d5db; }}
  .news-title {{
    font-size: 0.97rem;
    font-weight: 700;
    color: #111;
    line-height: 1.55;
  }}
  /* 情報テーブル */
  .info-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 0.85rem;
  }}
  .info-table td {{
    padding: 7px 10px;
    border: 1px solid #e5e7eb;
    vertical-align: top;
  }}
  .info-table td:first-child {{
    width: 90px;
    font-weight: 600;
    color: #6b7280;
    background: #f9fafb;
    white-space: nowrap;
  }}
  .info-table td:last-child {{ color: #1a1a1a; }}
  .stars {{ color: #f5a623; }}
  /* 投稿テンプレセクション */
  .template-section {{
    margin-top: 14px;
    border-top: 1px dashed #e5e7eb;
    padding-top: 14px;
  }}
  .template-section h4 {{
    font-size: 0.82rem;
    font-weight: 700;
    color: #6b7280;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .template-box {{
    background: #f9fafb;
    border: 1px solid #e5e7eb;
    border-left: 3px solid #e94560;
    border-radius: 0 6px 6px 0;
    padding: 10px 14px;
    font-size: 0.85rem;
    color: #374151;
    line-height: 1.7;
    margin-bottom: 8px;
  }}
  /* リンクボタン */
  .card-links {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 14px;
  }}
  .btn {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 6px 14px;
    border-radius: 6px;
    font-size: 0.8rem;
    text-decoration: none;
    font-weight: 500;
    transition: all 0.15s;
    border: 1px solid;
  }}
  .btn-news {{ background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }}
  .btn-news:hover {{ background: #2563eb; color: #fff; }}
  .btn-x {{ background: #f9fafb; color: #374151; border-color: #d1d5db; }}
  .btn-x:hover {{ background: #111; color: #fff; border-color: #111; }}
  /* まとめセクション */
  .tips-section {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 10px;
    padding: 20px 22px;
    margin-top: 32px;
  }}
  .tips-section h2 {{
    font-size: 1rem;
    font-weight: 700;
    color: #92400e;
    margin-bottom: 14px;
  }}
  .tips {{ list-style: none; }}
  .tips li {{
    padding: 8px 0;
    border-bottom: 1px solid #fde68a;
    font-size: 0.88rem;
    display: flex;
    gap: 10px;
    align-items: flex-start;
    color: #374151;
  }}
  .tips li:last-child {{ border-bottom: none; }}
  .tip-num {{
    background: #f5a623;
    color: #fff;
    font-weight: 700;
    font-size: 0.72rem;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 3px;
  }}
  footer {{
    text-align: center;
    padding: 24px;
    color: #9ca3af;
    font-size: 0.75rem;
    border-top: 1px solid #e5e7eb;
    margin-top: 40px;
  }}
  @media (max-width: 600px) {{
    .page-header, .container {{ padding-left: 16px; padding-right: 16px; }}
    .page-header h1 {{ font-size: 1.25rem; }}
    .info-table td:first-child {{ width: 70px; font-size: 0.78rem; }}
  }}
</style>
</head>
<body>
<div class="page-header">
  <h1>📊 株クラ朝刊 ── {date}</h1>
  <div class="meta">毎朝8時配信｜株クラ初心者向けトレンドニュース10選</div>
  <div class="desc">お金・働き方・投資の「今日の話題」をまとめました。Xの発信ネタにご活用ください。</div>
</div>
<div class="container">
  {date_nav}
  {trends_section}
  {news_cards}
  <div class="tips-section">
    <h2>📌 バズ投稿を作る3つのコツ</h2>
    <ul class="tips">
      <li><span class="tip-num">1</span><span>冒頭に<strong>「私も〇〇だった」という共感ストーリー</strong>を入れると伸びやすい</span></li>
      <li><span class="tip-num">2</span><span><strong>具体的な数字</strong>（〇〇円、〇〇%、〇〇万人）を使うとリアリティが増す</span></li>
      <li><span class="tip-num">3</span><span>最後に<strong>「あなたはどう思いますか？」</strong>と問いかけると返信が増える</span></li>
    </ul>
  </div>
</div>
<footer>
  <p>このレポートは自動生成されました。投資は自己責任でお願いします。</p>
  <p>生成日時: {generated_at}</p>
</footer>
</body>
</html>
"""

# =====================================================
# Markdownパース
# =====================================================
def parse_report(md_content):
    lines = md_content.split('\n')
    date = ""
    for line in lines[:5]:
        m = re.search(r'(\d{4}年\d{2}月\d{2}日[（(][月火水木金土日][）)]?)', line)
        if m:
            date = m.group(1)
            break

    generated_at = ""
    for line in lines:
        if '生成日時:' in line:
            generated_at = line.replace('*', '').replace('生成日時:', '').strip()
            break

    trends = []
    in_trends = False
    for line in lines:
        if '本日のGoogleトレンド' in line or '本日の株クラ注目トレンド' in line:
            in_trends = True
            continue
        if in_trends:
            if line.startswith('---') or (line.startswith('##') and 'トレンド' not in line):
                in_trends = False
                continue
            m = re.search(r'\*\*(.+?)\*\*.*?\[X検索\]\((.+?)\).*?\|\s*(\d+\+?)\s*\|', line)
            if m:
                trends.append({'keyword': m.group(1), 'x_url': m.group(2), 'traffic': m.group(3)})

    cat_class_map = {
        '税金': 'cat-tax', '制度': 'cat-tax',
        '退職': 'cat-work', '働き方': 'cat-work', 'Z世代': 'cat-z',
        '物価': 'cat-price', '生活費': 'cat-price',
        '給与': 'cat-salary', '年収': 'cat-salary',
        'NISA': 'cat-nisa', '投資入門': 'cat-nisa',
        '株式市場': 'cat-market', 'マクロ': 'cat-macro',
    }

    news = []
    current = {}
    for line in lines:
        m = re.match(r'^## (\d+)\. \[(.+?)\] (.+)', line)
        if m:
            if current:
                news.append(current)
            category = m.group(2)
            cat_class = 'cat-default'
            for key, cls in cat_class_map.items():
                if key in category:
                    cat_class = cls
                    break
            current = {
                'rank': int(m.group(1)), 'category': category, 'cat_class': cat_class,
                'title': m.group(3).split(' - ')[0][:70],
                'summary': '', 'hook': '', 'buzz_reason': '',
                'template': '', 'score': 5, 'stars': '⭐⭐⭐⭐⭐',
                'news_url': '#', 'x_url': '#'
            }
            continue
        if not current:
            continue
        if '**一言要約**' in line:
            current['summary'] = re.sub(r'.*\*\*一言要約\*\*\s*\|\s*(.+?)\s*\|.*', r'\1', line).strip()
        elif '**Xフック文**' in line:
            current['hook'] = re.sub(r'.*\*\*Xフック文\*\*\s*\|\s*(.+?)\s*\|.*', r'\1', line).strip()
        elif '**バズる理由**' in line:
            current['buzz_reason'] = re.sub(r'.*\*\*バズる理由\*\*\s*\|\s*(.+?)\s*\|.*', r'\1', line).strip()
        elif '**バズスコア**' in line:
            m2 = re.search(r'\((\d+)/10\)', line)
            if m2:
                score = int(m2.group(1))
                current['score'] = score
                current['stars'] = '⭐' * score
        elif line.startswith('> ') and current.get('hook') and not current.get('template'):
            current['template'] = line[2:].strip()
        elif '🔗 **ニュース原文**' in line or '🔗 ニュース原文' in line:
            m2 = re.search(r'\(https?://[^\)]+\)', line)
            if m2:
                current['news_url'] = m2.group()[1:-1]
        elif '🐦 **Xバズ投稿を探す**' in line or '🐦 Xバズ投稿を探す' in line:
            m2 = re.search(r'\(https?://[^\)]+\)', line)
            if m2:
                current['x_url'] = m2.group()[1:-1]
    if current:
        news.append(current)

    return date, trends, news, generated_at


def escape_html(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# =====================================================
# HTMLを生成する
# =====================================================
def generate_html(md_content, date_file, all_date_files):
    date, trends, news, generated_at = parse_report(md_content)    # 日付ナビ
    import time as _time
    cache_buster = str(int(_time.time()))
    nav_items = []
    for d in sorted(all_date_files, reverse=True)[:7]:  # 最新7件
        label = f"{d[:4]}/{d[4:6]}/{d[6:]}"
        active = 'active' if d == date_file else ''
        nav_items.append(f'<a href="{d}.html?v={cache_buster}" class="{active}">{label}</a>')
    date_nav = f'<div class="date-nav">{""  .join(nav_items)}</div>' if nav_items else ''

    # トレンドセクション
    if trends:
        tags = ''.join(
            f'<a href="{t["x_url"]}" target="_blank" class="trend-tag">'
            f'{escape_html(t["keyword"])}<span class="traffic">{t["traffic"]}</span></a>'
            for t in trends
        )
        trends_section = f'<div class="trends-section"><h2>🔥 本日のGoogleトレンド（日本）</h2><div class="trend-tags">{tags}</div></div>'
    else:
        trends_section = ''

    # ニュースカード
    cards = []
    for i, item in enumerate(news, 1):
        rank_class = 'gold' if i == 1 else 'silver' if i == 2 else 'bronze' if i == 3 else ''
        template_html = f'<div class="template-box">{escape_html(item["template"])}</div>' if item.get('template') else ''
        buzz_reason_row = f'<tr><td>バズる理由</td><td>{escape_html(item["buzz_reason"])}</td></tr>' if item.get('buzz_reason') else ''
        card = f"""
<div class="news-card">
  <div class="card-header">
    <div class="rank {rank_class}">{i}</div>
    <div class="card-title">
      <span class="category-badge {item['cat_class']}">{escape_html(item['category'])}</span>
      <div class="news-title">{escape_html(item['title'])}</div>
    </div>
  </div>
  <table class="info-table">
    <tr><td>一言要約</td><td>{escape_html(item['summary'])}</td></tr>
    <tr><td>Xフック文</td><td><strong>{escape_html(item['hook'])}</strong></td></tr>
    {buzz_reason_row}
    <tr><td>バズスコア</td><td><span class="stars">{item['stars']}</span> ({item['score']}/10)</td></tr>
  </table>
  {f'<div class="template-section"><h4>📝 投稿候補（パターA）</h4>{template_html}</div>' if item.get('template') else ''}
  <div class="card-links">
    <a href="{item['news_url']}" target="_blank" class="btn btn-news">🔗 ニュース原文</a>
    <a href="{item['x_url']}" target="_blank" class="btn btn-x">𝕏 Xで検索</a>
  </div>
</div>"""
        cards.append(card)

    html = HTML_TEMPLATE.format(
        date=escape_html(date),
        date_nav=date_nav,
        trends_section=trends_section,
        news_cards='\n'.join(cards),
        generated_at=escape_html(generated_at)
    )
    return html


# =====================================================
# GitHub Pagesにプッシュ
# =====================================================
def push_to_github(date_file, token):
    """生成したHTMLをgit push してGitHub Pagesに公開"""
    if not token:
        print("[SKIP] GITHUB_TOKEN未設定のためプッシュをスキップ")
        return None

    # リポジトリのリモートURLにトークンを埋め込む
    remote_url = f"https://{GITHUB_USER}:{token}@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"

    try:
        # 最新をpull
        subprocess.run(
            ["git", "-C", REPO_DIR, "pull", "--rebase", remote_url, "main"],
            capture_output=True, timeout=60
        )

        # reportsディレクトリのMDファイルを同期
        reports_src = REPORTS_DIR
        reports_dst = os.path.join(REPO_DIR, "reports")
        os.makedirs(reports_dst, exist_ok=True)
        for md_file in glob.glob(os.path.join(reports_src, "kabukura_news_*.md")):
            dst = os.path.join(reports_dst, os.path.basename(md_file))
            with open(md_file, encoding='utf-8') as f:
                content = f.read()
            with open(dst, 'w', encoding='utf-8') as f:
                f.write(content)

        # 全MDからHTMLを再生成
        all_md_files = glob.glob(os.path.join(reports_src, "kabukura_news_*.md"))
        all_date_files = [os.path.basename(f).replace("kabukura_news_", "").replace(".md", "") for f in all_md_files]

        for md_file in all_md_files:
            df = os.path.basename(md_file).replace("kabukura_news_", "").replace(".md", "")
            with open(md_file, encoding='utf-8') as f:
                md_content = f.read()
            html = generate_html(md_content, df, all_date_files)
            html_path = os.path.join(REPO_DIR, f"{df}.html")
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"[OK] HTML生成: {html_path}")

        # index.html = 最新日付にリダイレクト
        latest_date = sorted(all_date_files, reverse=True)[0]
        index_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={latest_date}.html">
<title>株クラ朝刊</title></head>
<body><a href="{latest_date}.html">最新の朝刊はこちら</a></body></html>"""
        with open(os.path.join(REPO_DIR, "index.html"), 'w', encoding='utf-8') as f:
            f.write(index_html)

        # git add & commit & push
        subprocess.run(["git", "-C", REPO_DIR, "add", "."], capture_output=True)
        result = subprocess.run(
            ["git", "-C", REPO_DIR, "commit", "-m", f"朝刊更新: {date_file}"],
            capture_output=True, text=True
        )
        if "nothing to commit" in result.stdout:
            print("[INFO] 変更なし（コミットスキップ）")
        else:
            push_result = subprocess.run(
                ["git", "-C", REPO_DIR, "push", remote_url, "main"],
                capture_output=True, text=True, timeout=60
            )
            if push_result.returncode == 0:
                print(f"[OK] GitHub Pagesにプッシュ完了")
            else:
                print(f"[ERROR] プッシュ失敗: {push_result.stderr}")
                return None

        page_url = f"{GITHUB_PAGES_BASE}/{date_file}.html"
        print(f"[OK] 公開URL: {page_url}")
        return page_url

    except Exception as e:
        print(f"[ERROR] GitHub push エラー: {e}")
        return None


# =====================================================
# LINEに送信
# =====================================================
def send_to_line(report_md, date_str, page_url):
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
        res = requests.post(api_url, headers=headers, json=data)
        if res.status_code == 200:
            print(f"[OK] LINE送信成功: {page_url}")
            return True
        else:
            print(f"[ERROR] LINE送信失敗: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"[ERROR] LINE送信エラー: {e}")
        return False


# =====================================================
# メイン
# =====================================================
def main():
    import sys
    token = GITHUB_TOKEN or (sys.argv[1] if len(sys.argv) > 1 else "")

    # 最新レポートを取得
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, "kabukura_news_*.md")), reverse=True)
    if not files:
        print("[ERROR] レポートファイルが見つかりません")
        return

    latest = files[0]
    date_file = os.path.basename(latest).replace("kabukura_news_", "").replace(".md", "")
    print(f"[INFO] 対象レポート: {latest}")

    with open(latest, encoding='utf-8') as f:
        report_md = f.read()

    # date_str を取得
    first_line = report_md.split("\n")[0]
    date_str = first_line.replace("# 📊 株クラ朝刊 ── ", "").strip()

    # GitHub Pagesにプッシュ
    page_url = push_to_github(date_file, token)

    if page_url:
        # LINEに送信
        send_to_line(report_md, date_str, page_url)
    else:
        # フォールバック: 現在のFlaskサーバーURLを使用
        fallback_url = f"https://7860-ioxe56me9j2jd1b2p947b-9d9d4812.sg1.manus.computer/{date_file}"
        print(f"[INFO] フォールバックURL使用: {fallback_url}")
        send_to_line(report_md, date_str, fallback_url)


if __name__ == "__main__":
    main()
