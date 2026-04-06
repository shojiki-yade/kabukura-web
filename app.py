# -*- coding: utf-8 -*-
"""
株クラ朝刊 - Web配信サーバー
MarkdownレポートをHTMLとして公開するFlaskアプリ
"""

from flask import Flask, render_template_string, abort
import os
import re
import glob

app = Flask(__name__)
REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 株クラ朝刊 {{ date }}</title>
<style>
  :root {
    --primary: #1a1a2e;
    --accent: #e94560;
    --gold: #f5a623;
    --bg: #0f0f1a;
    --card: #16213e;
    --text: #e0e0e0;
    --muted: #8888aa;
    --border: #2a2a4a;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Hiragino Kaku Gothic ProN', 'Noto Sans JP', sans-serif;
    line-height: 1.7;
  }
  header {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
    padding: 32px 20px 24px;
    text-align: center;
    border-bottom: 2px solid var(--accent);
  }
  header h1 { font-size: clamp(1.4rem, 4vw, 2rem); color: #fff; letter-spacing: 0.05em; }
  header h1 span { color: var(--gold); }
  header p { color: var(--muted); font-size: 0.85rem; margin-top: 6px; }
  .badge {
    display: inline-block;
    background: var(--accent);
    color: #fff;
    font-size: 0.7rem;
    padding: 2px 10px;
    border-radius: 20px;
    margin-top: 8px;
    letter-spacing: 0.08em;
  }
  .container { max-width: 800px; margin: 0 auto; padding: 24px 16px 60px; }

  .trends-section {
    background: var(--card);
    border: 1px solid var(--border);
    border-left: 4px solid var(--accent);
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 28px;
  }
  .trends-section h2 { font-size: 1rem; color: var(--accent); margin-bottom: 14px; }
  .trend-tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .trend-tag {
    background: #1a1a3e;
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 4px 14px;
    font-size: 0.82rem;
    color: var(--text);
    text-decoration: none;
    transition: all 0.2s;
  }
  .trend-tag:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
  .trend-tag .traffic { color: var(--gold); font-size: 0.72rem; margin-left: 4px; }

  .news-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 22px 20px;
    margin-bottom: 20px;
    transition: transform 0.2s, box-shadow 0.2s;
  }
  .news-card:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(233,69,96,0.15); }
  .card-header { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 14px; }
  .rank {
    background: linear-gradient(135deg, var(--accent), #c0392b);
    color: #fff;
    font-size: 1.1rem;
    font-weight: bold;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .rank.gold { background: linear-gradient(135deg, #f5a623, #e67e22); }
  .rank.silver { background: linear-gradient(135deg, #bdc3c7, #95a5a6); color: #333; }
  .rank.bronze { background: linear-gradient(135deg, #cd7f32, #a04000); }
  .card-title { flex: 1; }
  .category-badge {
    display: inline-block;
    font-size: 0.7rem;
    padding: 2px 10px;
    border-radius: 12px;
    margin-bottom: 6px;
    font-weight: bold;
  }
  .cat-tax { background: #3d1a1a; color: #ff8080; border: 1px solid #ff4444; }
  .cat-work { background: #1a2d1a; color: #80ff80; border: 1px solid #44aa44; }
  .cat-price { background: #1a1a3d; color: #8080ff; border: 1px solid #4444ff; }
  .cat-salary { background: #2d2d1a; color: #ffff80; border: 1px solid #aaaa44; }
  .cat-nisa { background: #1a2d2d; color: #80ffff; border: 1px solid #44aaaa; }
  .cat-market { background: #2d1a2d; color: #ff80ff; border: 1px solid #aa44aa; }
  .cat-macro { background: #2d1a1a; color: #ffaa80; border: 1px solid #aa6644; }
  .cat-z { background: #1a1a2d; color: #aaaaff; border: 1px solid #6666cc; }
  .cat-default { background: #1a1a1a; color: #aaaaaa; border: 1px solid #555; }
  .news-title { font-size: 0.95rem; font-weight: bold; color: #fff; line-height: 1.5; }
  .score-bar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
  .score-label { font-size: 0.72rem; color: var(--muted); }
  .stars { color: var(--gold); font-size: 0.9rem; letter-spacing: 1px; }
  .summary {
    background: #0a0a1a;
    border-left: 3px solid var(--gold);
    padding: 10px 14px;
    border-radius: 0 8px 8px 0;
    font-size: 0.9rem;
    color: #ddd;
    margin-bottom: 12px;
  }
  .hook {
    background: linear-gradient(135deg, #1a0a0a, #2a0a0a);
    border: 1px solid #cc3333;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 0.88rem;
    color: #ffcccc;
    margin-bottom: 12px;
    font-weight: bold;
  }
  .hook::before { content: "🔥 Xフック文: "; color: var(--accent); }
  .template {
    background: #0a1a0a;
    border: 1px solid #336633;
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 0.85rem;
    color: #ccffcc;
    margin-bottom: 14px;
    font-style: italic;
  }
  .template::before { content: "📝 投稿テンプレ: "; color: #66cc66; font-style: normal; font-weight: bold; }
  .buzz-reason { font-size: 0.75rem; color: var(--muted); margin-bottom: 10px; }
  .buzz-reason span { color: var(--gold); }
  .card-links { display: flex; gap: 10px; flex-wrap: wrap; }
  .btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 16px;
    border-radius: 20px;
    font-size: 0.8rem;
    text-decoration: none;
    font-weight: bold;
    transition: all 0.2s;
  }
  .btn-news { background: #1a3a5c; color: #7ab8ff; border: 1px solid #2a5a8c; }
  .btn-news:hover { background: #2a5a8c; color: #fff; }
  .btn-x { background: #1a1a1a; color: #aaa; border: 1px solid #333; }
  .btn-x:hover { background: #333; color: #fff; }

  .summary-section {
    background: var(--card);
    border: 1px solid var(--border);
    border-top: 3px solid var(--gold);
    border-radius: 10px;
    padding: 24px 20px;
    margin-top: 32px;
  }
  .summary-section h2 { color: var(--gold); margin-bottom: 16px; }
  .tips { list-style: none; }
  .tips li {
    padding: 10px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.9rem;
    display: flex;
    gap: 10px;
    align-items: flex-start;
  }
  .tips li:last-child { border-bottom: none; }
  .tip-num {
    background: var(--gold);
    color: #000;
    font-weight: bold;
    font-size: 0.75rem;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    margin-top: 2px;
  }
  .date-nav {
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 24px;
  }
  .date-nav a {
    background: var(--card);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 0.82rem;
    text-decoration: none;
    transition: all 0.2s;
  }
  .date-nav a.active, .date-nav a:hover { background: var(--accent); border-color: var(--accent); color: #fff; }
  footer {
    text-align: center;
    padding: 20px;
    color: var(--muted);
    font-size: 0.75rem;
    border-top: 1px solid var(--border);
  }
</style>
</head>
<body>
<header>
  <h1>📊 株クラ朝刊 <span>{{ date }}</span></h1>
  <p>お金・働き方・投資の「今日の話題」をまとめました</p>
  <span class="badge">毎朝8時配信 ｜ 株クラ初心者向けトレンドニュース10選</span>
</header>

<div class="container">
  {% if dates|length > 1 %}
  <div class="date-nav">
    {% for d in dates %}
    <a href="/{{ d }}" {% if d == current_date %}class="active"{% endif %}>{{ d[:4] }}/{{ d[4:6] }}/{{ d[6:] }}</a>
    {% endfor %}
  </div>
  {% endif %}

  {% if trends %}
  <div class="trends-section">
    <h2>🔥 本日のGoogleトレンド（日本）</h2>
    <div class="trend-tags">
      {% for t in trends %}
      <a href="{{ t.x_url }}" target="_blank" class="trend-tag">
        {{ t.keyword }}<span class="traffic">{{ t.traffic }}</span>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% for item in news %}
  <div class="news-card">
    <div class="card-header">
      <div class="rank {% if loop.index == 1 %}gold{% elif loop.index == 2 %}silver{% elif loop.index == 3 %}bronze{% endif %}">{{ loop.index }}</div>
      <div class="card-title">
        <span class="category-badge {{ item.cat_class }}">{{ item.category }}</span>
        <div class="news-title">{{ item.title }}</div>
      </div>
    </div>
    <div class="score-bar">
      <span class="score-label">バズスコア</span>
      <span class="stars">{{ item.stars }}</span>
      <span class="score-label">({{ item.score }}/10)</span>
    </div>
    <div class="summary">{{ item.summary }}</div>
    <div class="hook">{{ item.hook }}</div>
    {% if item.buzz_reason %}
    <div class="buzz-reason">💡 バズる理由: <span>{{ item.buzz_reason }}</span></div>
    {% endif %}
    <div class="template">{{ item.template }}</div>
    <div class="card-links">
      <a href="{{ item.news_url }}" target="_blank" class="btn btn-news">🔗 ニュース原文</a>
      <a href="{{ item.x_url }}" target="_blank" class="btn btn-x">𝕏 Xで検索</a>
    </div>
  </div>
  {% endfor %}

  <div class="summary-section">
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
  <p>生成日時: {{ generated_at }}</p>
</footer>
</body>
</html>
"""

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
        if '本日のGoogleトレンド' in line:
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
        elif '🔗 **ニュース原文**' in line:
            m2 = re.search(r'\(https?://[^\)]+\)', line)
            if m2:
                current['news_url'] = m2.group()[1:-1]
        elif '🐦 **Xバズ投稿を探す**' in line:
            m2 = re.search(r'\(https?://[^\)]+\)', line)
            if m2:
                current['x_url'] = m2.group()[1:-1]

    if current:
        news.append(current)

    return date, trends, news, generated_at


@app.route('/')
def index():
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, 'kabukura_news_*.md')), reverse=True)
    if not files:
        abort(404)
    date_key = os.path.basename(files[0]).replace('kabukura_news_', '').replace('.md', '')
    return show_report(date_key)


@app.route('/<date_key>')
def show_date(date_key):
    return show_report(date_key)


def show_report(date_key):
    filepath = os.path.join(REPORTS_DIR, f'kabukura_news_{date_key}.md')
    if not os.path.exists(filepath):
        abort(404)
    with open(filepath, encoding='utf-8') as f:
        content = f.read()
    date, trends, news, generated_at = parse_report(content)
    files = sorted(glob.glob(os.path.join(REPORTS_DIR, 'kabukura_news_*.md')), reverse=True)
    dates = [os.path.basename(f).replace('kabukura_news_', '').replace('.md', '') for f in files]
    return render_template_string(
        HTML_TEMPLATE,
        date=date, trends=trends, news=news,
        generated_at=generated_at, dates=dates, current_date=date_key
    )


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 7860))
    app.run(host='0.0.0.0', port=port, debug=False)
