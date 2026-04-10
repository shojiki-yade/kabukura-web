#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""株クラ朝刊 自動生成スクリプト v3
- Google News RSS から直近5日間の記事を取得
- GPT-4.1-mini で10本選定 + 一言要約 + 投稿3パターン生成
- Markdown と HTML を生成して保存
- LINE 送信は別スクリプト (publish_to_github.py) で実施
"""

import os
import sys
import io
import json
import re
import datetime
import urllib.parse
import email.utils
import html as html_escape_mod

import feedparser
from openai import OpenAI

# UTF-8 出力（Windows対応）
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

# .env が存在すればロード（ローカル実行用）
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))
except ImportError:
    pass

if not os.environ.get("OPENAI_API_KEY"):
    print("[ERROR] OPENAI_API_KEY が設定されていません")
    sys.exit(1)

# リポジトリルート（このファイルの2つ上）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
REPORTS_DIR = os.path.join(REPO_ROOT, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

client = OpenAI()


# =====================================================
# ニュース取得クエリ（短い2語ペアで広く拾う）
# =====================================================
NEWS_QUERIES = [
    {"query": "芸能人 相続", "label": "芸能人×お金"},
    {"query": "有名人 遺産", "label": "芸能人×お金"},
    {"query": "タレント 破産", "label": "芸能人×お金"},
    {"query": "芸能人 資産", "label": "芸能人×お金"},
    {"query": "有名人 借金", "label": "芸能人×お金"},
    {"query": "芸能人 節税", "label": "芸能人×お金"},

    {"query": "退職代行 新入社員", "label": "退職・働き方"},
    {"query": "初日 退職", "label": "退職・働き方"},
    {"query": "早期退職 若手", "label": "退職・働き方"},
    {"query": "ブラック企業 残業", "label": "退職・働き方"},
    {"query": "パワハラ 会社", "label": "退職・働き方"},
    {"query": "給料未払い", "label": "退職・働き方"},

    {"query": "4月 制度変更", "label": "制度・ルール変更"},
    {"query": "4月 値上げ", "label": "制度・ルール変更"},
    {"query": "制度 改正", "label": "制度・ルール変更"},
    {"query": "補助金 廃止", "label": "制度・ルール変更"},

    {"query": "健康保険料 増加", "label": "税金・手取り"},
    {"query": "手取り 減少", "label": "税金・手取り"},
    {"query": "増税 サラリーマン", "label": "税金・手取り"},
    {"query": "社会保険料 負担", "label": "税金・手取り"},

    {"query": "平均貯蓄 格差", "label": "お金の格差・実態"},
    {"query": "平均年収 実態", "label": "お金の格差・実態"},
    {"query": "老後資金 2000万円", "label": "お金の格差・実態"},
    {"query": "貯蓄ゼロ 世帯", "label": "お金の格差・実態"},
    {"query": "老後破産", "label": "お金の格差・実態"},

    {"query": "食費 値上げ", "label": "物価・生活費"},
    {"query": "電気代 高騰", "label": "物価・生活費"},
    {"query": "物価上昇 家計", "label": "物価・生活費"},
    {"query": "ガス代 値上げ", "label": "物価・生活費"},

    {"query": "知らないと損", "label": "節約・お得情報"},
    {"query": "節約 やめた", "label": "節約・お得情報"},
    {"query": "無駄 出費", "label": "節約・お得情報"},

    {"query": "新NISA 後悔", "label": "NISA・投資入門"},
    {"query": "NISA 失敗", "label": "NISA・投資入門"},
    {"query": "NISA 初心者", "label": "NISA・投資入門"},
    {"query": "投資 やめた", "label": "NISA・投資入門"},

    {"query": "テスラ EV", "label": "テクノロジー"},
    {"query": "スマホ 新製品", "label": "テクノロジー"},
    {"query": "半導体 最新", "label": "テクノロジー"},
    {"query": "ロボット 新技術", "label": "テクノロジー"},
    {"query": "宇宙 ロケット", "label": "テクノロジー"},

    {"query": "円安 株価", "label": "経済"},
    {"query": "日銀 金利", "label": "経済"},
    {"query": "景気 悪化", "label": "経済"},
    {"query": "企業 決算", "label": "経済"},
    {"query": "倒産 企業", "label": "経済"},
    {"query": "リストラ 大手", "label": "経済"},

    {"query": "Netflix 決算", "label": "エンタメ"},
    {"query": "映画 興行収入", "label": "エンタメ"},
    {"query": "ABEMA 黒字", "label": "エンタメ"},
    {"query": "推し活 出費", "label": "エンタメ"},
    {"query": "芸能人 ギャラ", "label": "エンタメ"},
    {"query": "映画館 値上げ", "label": "エンタメ"},
]

CATEGORY_CSS = {
    "芸能人×お金": "cat-default",
    "退職・働き方": "cat-work",
    "制度・ルール変更": "cat-tax",
    "税金・手取り": "cat-salary",
    "お金の格差・実態": "cat-default",
    "物価・生活費": "cat-price",
    "節約・お得情報": "cat-default",
    "NISA・投資入門": "cat-nisa",
    "テクノロジー": "cat-z",
    "経済": "cat-market",
    "エンタメ": "cat-macro",
}


# =====================================================
# データ取得
# =====================================================
def fetch_news(queries, max_per_query=8):
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_jst = datetime.datetime.now(jst)
    start_date_jst = (now_jst - datetime.timedelta(days=4)).date()
    after_date = start_date_jst.strftime("%Y-%m-%d")
    cutoff_dt = datetime.datetime.combine(start_date_jst, datetime.time.min).replace(tzinfo=jst)

    all_news = []
    seen_titles = set()

    def fetch_one(q):
        query_with_date = f"{q['query']} after:{after_date}"
        encoded = urllib.parse.quote(query_with_date)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
                continue
            # 「AI」関連記事を除外
            if "AI" in title or "ＡＩ" in title or "人工知能" in title or "ChatGPT" in title or "生成ai" in title.lower():
                continue
            key = title[:50]
            if key in seen_titles:
                continue
            pub_str = entry.get("published", "")
            if pub_str:
                try:
                    pub_jst = email.utils.parsedate_to_datetime(pub_str).astimezone(jst)
                    if pub_jst < cutoff_dt:
                        continue
                except Exception:
                    pass
            results.append({
                "title": title,
                "link": entry.get("link", ""),
                "published": pub_str,
                "source": entry.get("source", {}).get("title", ""),
                "label": q["label"],
                "query": q["query"],
                "key": key,
            })
            if len(results) >= max_per_query:
                break
        return results

    print(f"[RANGE] {after_date} 〜 {now_jst.strftime('%Y-%m-%d')}（直近5日間）")
    category_counts = {}
    for q in queries:
        results = fetch_one(q)
        if not results:
            print(f"  [INFO] {q['label']} / {q['query'][:24]}: 記事なし")
        for r in results:
            if r["key"] not in seen_titles:
                seen_titles.add(r["key"])
                all_news.append({k: v for k, v in r.items() if k != "key"})
                category_counts[q["label"]] = category_counts.get(q["label"], 0) + 1

    print(f"[SUMMARY] カテゴリ別: {dict(sorted(category_counts.items()))}")
    return all_news


def fetch_google_trends(max_count=10):
    trends = []
    seen = set()
    url = 'https://trends.google.co.jp/trending/rss?geo=JP'
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            kw = entry.get('title', '').strip()
            traffic = entry.get('ht_approx_traffic', '')
            if kw and kw not in seen:
                seen.add(kw)
                trends.append({
                    'keyword': kw,
                    'traffic': traffic,
                    'x_search_url': f"https://x.com/search?q={urllib.parse.quote(kw)}&src=typed_query&f=top"
                })
            if len(trends) >= max_count:
                break
    except Exception as e:
        print(f"[WARN] トレンド取得エラー: {e}")
    return trends


def format_pub_date(pub_str):
    if not pub_str:
        return ""
    try:
        dt = email.utils.parsedate_to_datetime(pub_str)
        jst = datetime.timezone(datetime.timedelta(hours=9))
        return dt.astimezone(jst).strftime("%Y/%m/%d")
    except Exception:
        return pub_str[:16]


def esc(s):
    return html_escape_mod.escape(s or "", quote=True)


# =====================================================
# AI選定・要約・投稿文生成
# =====================================================
def ai_select_and_summarize(news_list, target_count=10):
    news_json = json.dumps(
        [{"id": i, "title": n["title"], "label": n["label"], "source": n["source"]}
         for i, n in enumerate(news_list)],
        ensure_ascii=False
    )

    prompt = f"""あなたはXで「株クラ初心者向けお金アカウント」を運営するプロのSNSマーケターです。

【読者層】20〜40代会社員・主婦・投資初心者。難しい投資用語より生活に直結するお金の話に反応する。

【理想のニュースの粒度】
✅ 芸能人 × お金（遺産・相続・破産・資産公開・高額収入）
✅ 「えっそんなに？」驚きの数字（平均貯蓄・格差・損した金額）
✅ 「知らないと損する」制度変更（4月から変わること等）
✅ 共感・炎上の働き方ニュース（退職代行・ブラック企業）
✅ 生活直撃の値上げ・物価（食費・電気代・具体的品目）
✅ NISA・投資入門（やわらかい切り口限定）
✅ テクノロジー（EV・半導体・スマホ・ロボット・宇宙など生活に与える影響。ただしAI関連は除外）
✅ 経済（株価・金利・企業倒産など一般人に影響あるもの）
✅ エンタメ（話題のドラマ・映画・芸能）

❌ 避けるニュース
- AI・人工知能・ChatGPT・生成AIに関する記事（全て除外）
- 硬すぎる金融政策（FRB・長期金利◯%など）
- 副業紹介・副業おすすめ
- お金と無関係の芸能ゴシップ・エンタメ
- スポーツ結果、事件・事故・災害

【選定件数の絶対ルール（最重要）】
★必ずちょうど{target_count}本だけ選んでください。★
- {target_count-1}本でも{target_count+1}本でも不可。ちょうど{target_count}本。
- 返答のJSONの selected 配列の長さは厳密に {target_count} にしてください。

【カテゴリバランス（絶対順守・ハード制約）】
{target_count}本の中に以下のラベルは必ず各1本以上含めてください。バズスコアより優先。
- 「芸能人×お金」ラベル：必ず1本以上（ただしお金要素必須、下記参照）
- 「テクノロジー」ラベル：必ず1本以上
- 「経済」ラベル：必ず1本以上
- 「エンタメ」ラベル：**お金に絡む要素がある記事のみ**1本以上
該当ラベルがニュースリストに1本も存在しない場合のみ省略可。

「芸能人×お金」については、お金と無関係の純粋な芸能ゴシップは除外し、
必ず「相続・遺産・資産・破産・節税・借金・高額収入」いずれかに絡む記事を選ぶこと。

「エンタメ」については、以下のいずれかのお金要素がある記事のみ選ぶこと：
- 制作費・興行収入・配信サービスの売上や黒字化・決算（例: ABEMA黒字化、Netflix決算）
- 出演者のギャラ・契約金・印税
- 映画館やテーマパークの料金値上げ
- ファン経済・グッズ消費・推し活の出費
- 広告業界の動向
純粋な「話題のドラマが面白い」「俳優が出演する」だけの記事は絶対に選ばない。
お金要素のあるエンタメ記事がリストに1本もない場合は、エンタメは省略して他カテゴリで{target_count}本埋めること。

【同一トピックの重複排除（厳守）】
同じ話題は必ず1本に絞る。以下は同一トピックと判断：
- 同じ人物・同じ事件・同じ制度を扱っている（例: 中山美穂相続税、退職代行初日退職、大阪ガス値上げ）
- 情報源が違っても1本に統合し、最も詳しい・最新のものを選ぶ
- {target_count}本の中で同じ話題が2本以上出ないように必ず確認すること

【文体ルール（厳守・最重要）】
**全投稿を標準語のカジュアル口調で書くこと**。関西弁は使わない。
- NG例: 〜やん、〜あかん、〜してん、〜ねん、〜せぇ、〜やで、〜すぎん、〜へん、〜やろ、〜ちゃう
- OK例: 〜じゃん、〜だよね、〜だよ、〜でしょ、〜かな、〜よ、〜すぎる、〜ない、〜だろ、〜じゃない
- 「意味わからんすぎん？」ではなく「意味わからなすぎない？」または「意味わかんなくない？」
- 「何も信じられへん」ではなく「何も信じられない」
- 「〜せなあかんねん」ではなく「〜しなきゃいけないの？」
砕けた話し言葉はOK（「マジで」「ヤバい」「えっ」「マジか」など）。
でも関西弁の語尾・語彙は全部禁止。

【バズ投稿実例（すべて標準語）】
実例1: 「三菱商事に就職した同期が、飲み会の幹事でアサヒビール出すお店選んじゃってめちゃくちゃ怒られたって言ってた。数年前の話だけど流石にこれで降格、減給は無いよね？」
実例2: 「リボ払いだけは絶対しちゃダメってみんな言うけどさ、スマホとかの分割払いは別にいいの？後から払うならリボと同じじゃない？分割との違いってなに？？？」
実例3: 「ご近所さんに証券会社勤めの旦那さんがいるんだけど、夫婦揃ってNISA使ってないらしい。証券会社勤めってNISAしちゃダメな決まりあったっけ？」
実例4: 「NISAのリスクって「暴落して一文無しになること」よりも、コツコツ切り詰めて積立投資してきた結果「若い頃に散財してた人より年金少なくていいよな？」って後出しで言われる可能性のほうが高い気がしてる。」
実例5: 「年金ってなんで払った額以下しか貰えないの？？厚生年金は会社も払ってるのに謎。自分で残りの40年資産運用した方がよっぽどお金増えると思うんだけど...国って国民にはNISA勧めるくせに運用下手すぎない？？？？？」

共通ルール:
✅ 話し言葉・砕けた表現
✅ 疑問形終わり（「〜よね？」「〜あったっけ？」「〜なに？？？」）
✅ 固有名詞（企業名・制度名・金額）を入れてリアリティ
✅ 「みんな言うけど」で逆張り、「？？？」「？？？？？」で感情表現
✅ 中学生でも理解できる言葉。1ツイートで完結
❌ 「〜です」「〜ます」等の丁寧語NG
❌ 「投資をしましょう」等の説教口調NG
❌ ハッシュタグNG

【投稿3パターン】
■ パターンA「身近な実話・共感型」
- 「〇〇に勤めてる友達が〜」「ご近所の〇〇さんが〜」から始める
- 固有名詞でリアリティ、「〜よね？」等の疑問形終わり、140字以内

■ パターンB「逆張り・賛否型」
- 「〇〇ってみんな言うけどさ」「〜よりも〜の方が怖い気してる」から始める
- 「え、それって〜と同じじゃない？」で矛盾指摘、「？？？」「？？？？？」締め、140字以内

■ パターンC「怒り・問いかけ型」
- 「なんで〜の？？」「〜すぎない？？？？？」の感情から始める
- 具体的な数字（金額・年数・割合）を必ず1つ入れる、140字以内
- 【定型禁止】以下のフレーズは全投稿通じて**2回以上使うの禁止**：
  「国は〜しろ」「会社は〜しろ」「〜してくれ」
- パターンCの締めは以下のようにバリエーションを持たせる（すべて標準語）：
  a. 純粋な疑問「〜って意味わかんなくない？？？？？」
  b. 自己ツッコミ「〜って自分だけ？？？？？」
  c. 制度不信「これで国民に投資しろって無理ある気がする？？」
  d. 絶望系「もう何も信じられない？？？？？」
  e. 逆説「むしろ〜のほうがマシじゃない？？？」
  f. 呆れ「真面目に働くの馬鹿らしくない？？？」
  g. 疑問「〜って普通じゃないでしょ？？？」
  10本のパターンCで締め方をできるだけ重複させないこと。**同じ締めフレーズを3本以上で使うの禁止**。

以下のニュースリストから最もバズる**ちょうど{target_count}本**を選び、以下のJSON形式のみで返答してください:

{{
  "selected": [
    {{
      "id": <元のid>,
      "summary": "<40字以内の一言要約>",
      "hook": "<60字以内のXフック文。えっ/知らなかった/これは怒る等の感情>",
      "buzz_reason": "<30字以内>",
      "search_keyword": "<10字以内のX検索ワード>",
      "post_a": "<140字以内>",
      "post_b": "<140字以内>",
      "post_c": "<140字以内>",
      "score": <1-10>
    }}
  ]
}}

selected配列の長さは厳密に {target_count} にすること。

ニュースリスト:
{news_json}

JSONのみ返答してください。"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
    )
    raw = response.choices[0].message.content.strip()
    match = re.search(r'\{.*\}', raw, re.DOTALL)
    if match:
        result = json.loads(match.group())
        return result.get("selected", [])
    return []


# =====================================================
# Markdown 出力
# =====================================================
def generate_markdown(news_list, selected_items, date_str):
    lines = []
    lines.append(f"# 📊 株クラ朝刊 ── {date_str}")
    lines.append("")
    lines.append("> **株クラ初心者向けトレンドニュース10選**")
    lines.append("> 過去5日間の話題から厳選")
    lines.append("")
    lines.append("---")
    lines.append("")
    for rank, item in enumerate(selected_items, 1):
        news = news_list[item["id"]]
        keyword = item.get("search_keyword", "")
        lines.append(f"## {rank}. [{news['label']}] {news['title']}")
        lines.append("")
        lines.append("| 項目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| **一言要約** | {item['summary']} |")
        lines.append(f"| **Xフック文** | {item['hook']} |")
        lines.append(f"| **バズる理由** | {item['buzz_reason']} |")
        lines.append(f"| **バズスコア** | {'⭐' * item.get('score', 5)} ({item.get('score', 5)}/10) |")
        lines.append(f"| **情報源** | {news['source']}（{format_pub_date(news.get('published',''))}） |")
        lines.append("")
        lines.append("📝 **投稿候補3パターン**")
        lines.append("")
        lines.append("> **【パターンA】共感ストーリー型**")
        lines.append(f"> {item.get('post_a', '')}")
        lines.append("")
        lines.append("> **【パターンB】賛否・炎上型**")
        lines.append(f"> {item.get('post_b', '')}")
        lines.append("")
        lines.append("> **【パターンC】問いかけ・リプ狙い型**")
        lines.append(f"> {item.get('post_c', '')}")
        lines.append("")
        lines.append(f"🔗 **ニュース原文**: [{news['title'][:40]}...]({news['link']})")
        lines.append("")
        lines.append(f"🐦 **Xで検索**: [「{keyword}」で検索 →](https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=top)")
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


# =====================================================
# HTML 出力
# =====================================================
HTML_CSS = """
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: #ffffff; color: #1a1a1a; font-family: 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', sans-serif; line-height: 1.75; font-size: 15px; }
  .page-header { border-bottom: 1px solid #e5e7eb; padding: 28px 24px 20px; max-width: 780px; margin: 0 auto; }
  .page-header h1 { font-size: 1.6rem; font-weight: 700; color: #111; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .page-header .meta { margin-top: 6px; font-size: 0.82rem; color: #6b7280; }
  .page-header .desc { margin-top: 4px; font-size: 0.88rem; color: #374151; }
  .container { max-width: 780px; margin: 0 auto; padding: 24px 24px 80px; }
  .date-nav { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 28px; padding-bottom: 16px; border-bottom: 1px solid #e5e7eb; }
  .date-nav a { background: #f3f4f6; border: 1px solid #e5e7eb; color: #374151; padding: 4px 14px; border-radius: 20px; font-size: 0.8rem; text-decoration: none; transition: all 0.15s; }
  .date-nav a.active { background: #e94560; border-color: #e94560; color: #fff; font-weight: 600; }
  .date-nav a:hover:not(.active) { background: #e5e7eb; }
  .trends-section { background: #fafafa; border: 1px solid #e5e7eb; border-left: 4px solid #e94560; border-radius: 8px; padding: 16px 20px; margin-bottom: 32px; }
  .trends-section h2 { font-size: 0.95rem; font-weight: 700; color: #e94560; margin-bottom: 12px; }
  .trend-tags { display: flex; flex-wrap: wrap; gap: 8px; }
  .trend-tag { background: #fff; border: 1px solid #d1d5db; border-radius: 20px; padding: 3px 12px; font-size: 0.8rem; color: #374151; text-decoration: none; transition: all 0.15s; }
  .trend-tag:hover { background: #e94560; border-color: #e94560; color: #fff; }
  .trend-tag .traffic { color: #f5a623; font-size: 0.72rem; margin-left: 4px; }
  .news-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px 22px; margin-bottom: 20px; transition: box-shadow 0.15s; background: #fff; }
  .news-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
  .card-header { display: flex; align-items: flex-start; gap: 14px; margin-bottom: 12px; }
  .rank { background: #e94560; color: #fff; font-size: 0.9rem; font-weight: 700; width: 32px; height: 32px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 2px; }
  .rank.gold { background: #f5a623; }
  .rank.silver { background: #9ca3af; }
  .rank.bronze { background: #cd7f32; }
  .card-title { flex: 1; }
  .category-badge { display: inline-block; font-size: 0.7rem; padding: 2px 10px; border-radius: 20px; margin-bottom: 5px; font-weight: 600; background: #fee2e2; color: #dc2626; border: 1px solid #fca5a5; }
  .cat-tax { background: #fee2e2; color: #dc2626; border-color: #fca5a5; }
  .cat-work { background: #dcfce7; color: #16a34a; border-color: #86efac; }
  .cat-price { background: #dbeafe; color: #2563eb; border-color: #93c5fd; }
  .cat-salary { background: #fef9c3; color: #ca8a04; border-color: #fde047; }
  .cat-nisa { background: #cffafe; color: #0891b2; border-color: #67e8f9; }
  .cat-market { background: #f3e8ff; color: #9333ea; border-color: #d8b4fe; }
  .cat-macro { background: #ffedd5; color: #ea580c; border-color: #fdba74; }
  .cat-z { background: #e0e7ff; color: #4338ca; border-color: #a5b4fc; }
  .cat-default { background: #f3f4f6; color: #6b7280; border-color: #d1d5db; }
  .news-title { font-size: 0.97rem; font-weight: 700; color: #111; line-height: 1.55; }
  .info-table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.85rem; }
  .info-table td { padding: 7px 10px; border: 1px solid #e5e7eb; vertical-align: top; }
  .info-table td:first-child { width: 90px; font-weight: 600; color: #6b7280; background: #f9fafb; white-space: nowrap; }
  .info-table td:last-child { color: #1a1a1a; }
  .stars { color: #f5a623; }
  .template-section { margin-top: 14px; border-top: 1px dashed #e5e7eb; padding-top: 14px; }
  .template-section h4 { font-size: 0.82rem; font-weight: 700; color: #6b7280; margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
  .template-label { font-size: 0.72rem; font-weight: 700; color: #e94560; margin-top: 10px; margin-bottom: 4px; }
  .template-label:first-of-type { margin-top: 0; }
  .template-box { background: #f9fafb; border: 1px solid #e5e7eb; border-left: 3px solid #e94560; border-radius: 0 6px 6px 0; padding: 10px 14px; font-size: 0.85rem; color: #374151; line-height: 1.7; margin-bottom: 8px; }
  .card-links { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
  .btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border-radius: 6px; font-size: 0.8rem; text-decoration: none; font-weight: 500; transition: all 0.15s; border: 1px solid; }
  .btn-news { background: #eff6ff; color: #2563eb; border-color: #bfdbfe; }
  .btn-news:hover { background: #2563eb; color: #fff; }
  .btn-x { background: #f9fafb; color: #374151; border-color: #d1d5db; }
  .btn-x:hover { background: #111; color: #fff; border-color: #111; }
  .tips-section { background: #fffbeb; border: 1px solid #fde68a; border-radius: 10px; padding: 20px 22px; margin-top: 32px; }
  .tips-section h2 { font-size: 1rem; font-weight: 700; color: #92400e; margin-bottom: 14px; }
  .tips { list-style: none; }
  .tips li { padding: 8px 0; border-bottom: 1px solid #fde68a; font-size: 0.88rem; display: flex; gap: 10px; align-items: flex-start; color: #374151; }
  .tips li:last-child { border-bottom: none; }
  .tip-num { background: #f5a623; color: #fff; font-weight: 700; font-size: 0.72rem; width: 20px; height: 20px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; margin-top: 3px; }
  footer { text-align: center; padding: 24px; color: #9ca3af; font-size: 0.75rem; border-top: 1px solid #e5e7eb; margin-top: 40px; }
  @media (max-width: 600px) {
    .page-header, .container { padding-left: 16px; padding-right: 16px; }
    .page-header h1 { font-size: 1.25rem; }
    .info-table td:first-child { width: 70px; font-size: 0.78rem; }
  }
"""


def collect_existing_dates(repo_root, current_date_file):
    import glob
    pattern = os.path.join(repo_root, "????????.html")
    files = glob.glob(pattern)
    dates = set()
    for f in files:
        name = os.path.basename(f).replace(".html", "")
        if name.isdigit() and len(name) == 8:
            dates.add(name)
    dates.add(current_date_file)
    return sorted(dates, reverse=True)[:7]


def generate_html(news_list, selected_items, date_str, date_file, trends, repo_root):
    parts = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="ja">')
    parts.append('<head>')
    parts.append('<meta charset="UTF-8">')
    parts.append('<meta name="viewport" content="width=device-width, initial-scale=1.0">')
    parts.append('<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">')
    parts.append('<meta http-equiv="Pragma" content="no-cache">')
    parts.append('<meta http-equiv="Expires" content="0">')
    parts.append(f'<title>📊 株クラ朝刊 {esc(date_str)}</title>')
    parts.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
    parts.append('<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap" rel="stylesheet">')
    parts.append(f'<style>{HTML_CSS}</style>')
    parts.append('</head>')
    parts.append('<body>')

    parts.append('<div class="page-header">')
    parts.append(f'  <h1>📊 株クラ朝刊 ── {esc(date_str)}</h1>')
    parts.append('  <div class="meta">毎朝8時配信｜株クラ初心者向けトレンドニュース10選</div>')
    parts.append('  <div class="desc">お金・働き方・投資の「今日の話題」をまとめました。Xの発信ネタにご活用ください。</div>')
    parts.append('</div>')

    parts.append('<div class="container">')

    nav_dates = collect_existing_dates(repo_root, date_file)
    parts.append('  <div class="date-nav">')
    for d in nav_dates:
        label = f"{d[:4]}/{d[4:6]}/{d[6:]}"
        active_cls = 'active' if d == date_file else ''
        parts.append(f'    <a href="{d}.html" class="{active_cls}">{label}</a>')
    parts.append('  </div>')

    if trends:
        parts.append('  <div class="trends-section"><h2>🔥 本日のGoogleトレンド（日本）</h2><div class="trend-tags">')
        for t in trends:
            traffic_html = f'<span class="traffic">{esc(t.get("traffic",""))}</span>' if t.get("traffic") else ""
            parts.append(f'    <a href="{esc(t["x_search_url"])}" target="_blank" class="trend-tag">{esc(t["keyword"])}{traffic_html}</a>')
        parts.append('  </div></div>')

    for rank, item in enumerate(selected_items, 1):
        news = news_list[item["id"]]
        label = news["label"]
        cat_css = CATEGORY_CSS.get(label, "cat-default")
        rank_class = {1: "gold", 2: "silver", 3: "bronze"}.get(rank, "")
        score = item.get("score", 5)
        stars = "⭐" * score
        keyword = item.get("search_keyword", "")
        x_search_url = f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=top"

        parts.append('  <div class="news-card">')
        parts.append('    <div class="card-header">')
        parts.append(f'      <div class="rank {rank_class}">{rank}</div>')
        parts.append('      <div class="card-title">')
        parts.append(f'        <span class="category-badge {cat_css}">{esc(label)}</span>')
        parts.append(f'        <div class="news-title">{esc(news["title"])}</div>')
        parts.append('      </div>')
        parts.append('    </div>')
        parts.append('    <table class="info-table">')
        parts.append(f'      <tr><td>一言要約</td><td>{esc(item.get("summary",""))}</td></tr>')
        parts.append(f'      <tr><td>Xフック文</td><td><strong>{esc(item.get("hook",""))}</strong></td></tr>')
        parts.append(f'      <tr><td>バズる理由</td><td>{esc(item.get("buzz_reason",""))}</td></tr>')
        parts.append(f'      <tr><td>バズスコア</td><td><span class="stars">{stars}</span> ({score}/10)</td></tr>')
        parts.append(f'      <tr><td>情報源</td><td>{esc(news.get("source",""))}（{esc(format_pub_date(news.get("published","")))}）</td></tr>')
        parts.append('    </table>')
        parts.append('    <div class="template-section">')
        parts.append('      <h4>📝 投稿候補3パターン</h4>')
        parts.append('      <div class="template-label">【A】共感ストーリー型</div>')
        parts.append(f'      <div class="template-box">{esc(item.get("post_a",""))}</div>')
        parts.append('      <div class="template-label">【B】賛否・炎上型</div>')
        parts.append(f'      <div class="template-box">{esc(item.get("post_b",""))}</div>')
        parts.append('      <div class="template-label">【C】問いかけ・リプ狙い型</div>')
        parts.append(f'      <div class="template-box">{esc(item.get("post_c",""))}</div>')
        parts.append('    </div>')
        parts.append('    <div class="card-links">')
        parts.append(f'      <a href="{esc(news.get("link",""))}" target="_blank" class="btn btn-news">🔗 ニュース原文</a>')
        parts.append(f'      <a href="{esc(x_search_url)}" target="_blank" class="btn btn-x">𝕏 Xで検索</a>')
        parts.append('    </div>')
        parts.append('  </div>')

    parts.append('  <div class="tips-section">')
    parts.append('    <h2>📌 バズ投稿を作る3つのコツ</h2>')
    parts.append('    <ul class="tips">')
    parts.append('      <li><span class="tip-num">1</span><span>冒頭に<strong>「私も〇〇だった」という共感ストーリー</strong>を入れると伸びやすい</span></li>')
    parts.append('      <li><span class="tip-num">2</span><span><strong>具体的な数字</strong>（〇〇円、〇〇%、〇〇万人）を使うとリアリティが増す</span></li>')
    parts.append('      <li><span class="tip-num">3</span><span>最後に<strong>「あなたはどう思いますか？」</strong>と問いかけると返信が増える</span></li>')
    parts.append('    </ul>')
    parts.append('  </div>')
    parts.append('</div>')

    now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M")
    parts.append('<footer>')
    parts.append('  <p>このレポートは自動生成されました。投資は自己責任でお願いします。</p>')
    parts.append(f'  <p>生成日時: {now_str}</p>')
    parts.append('</footer>')
    parts.append('</body>')
    parts.append('</html>')
    return "\n".join(parts)


# =====================================================
# メイン
# =====================================================
def main():
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now = datetime.datetime.now(jst)
    weekday_ja = "月火水木金土日"[now.weekday()]
    date_str = now.strftime("%Y年%m月%d日") + f"（{weekday_ja}）"
    date_file = now.strftime("%Y%m%d")

    print(f"[{now.strftime('%H:%M:%S')}] Googleトレンド取得...")
    trends = fetch_google_trends(max_count=10)
    print(f"  → {len(trends)}件")

    print(f"[{now.strftime('%H:%M:%S')}] ニュース取得...")
    news_list = fetch_news(NEWS_QUERIES, max_per_query=8)
    print(f"  → {len(news_list)}件取得")

    if not news_list:
        print("[ERROR] ニュースなし")
        sys.exit(1)

    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] AI選定中...")
    selected = ai_select_and_summarize(news_list, target_count=10)
    print(f"  → {len(selected)}件選定")
    if not selected:
        print("[ERROR] AI選定失敗")
        sys.exit(1)

    selected.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected = selected[:10]

    md = generate_markdown(news_list, selected, date_str)
    md_path = os.path.join(REPORTS_DIR, f"kabukura_news_{date_file}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[OK] MD: {md_path}")

    html = generate_html(news_list, selected, date_str, date_file, trends, REPO_ROOT)
    html_path = os.path.join(REPO_ROOT, f"{date_file}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[OK] HTML: {html_path}")


if __name__ == "__main__":
    main()
