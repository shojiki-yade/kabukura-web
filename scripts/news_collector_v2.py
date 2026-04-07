#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
株クラ朝刊 v3 - 「一般人でも関心のあるお金ニュース」最適化版
参考: 中山美穂×相続税55%（感情×具体的数字）、退職代行×初日（共感×炎上）
"""

import os
import json
import datetime
import feedparser
import re
from openai import OpenAI

# =====================================================
# 設定
# =====================================================
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "hf+HsyL6s3roeP1QKflE3RDiPwuQBxQSMb51uALi4oGHeGG/aqcxRy2rXXsZORgvwvG31wkEFIEB1XepTfx/dCTEJRBoJQpLlmsJHkL1Uc5qT1HmFY8fdkmWgJLbAQ5swH4vU2DoOrjkIimGlPhYhgdB04t89/1O/w1cDnyilFU=")
LINE_GROUP_ID = os.environ.get("LINE_GROUP_ID", "C4f779e049966034f8bdf83b08139cf2c")

# 朝刊WebページのベースURL（毎朝8時に自動公開されるURL）
WEB_BASE_URL = os.environ.get("KABUKURA_WEB_URL", "https://7860-ioxe56me9j2jd1b2p947b-9d9d4812.sg1.manus.computer")

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

client = OpenAI()

# =====================================================
# ニュース収集クエリ（v3: 「友達に話したくなるお金ネタ」最適化）
# =====================================================
# 【設計思想】
# ✅ 芸能人・有名人 × お金（相続・破産・資産公開）
# ✅ 「ぼったくり？」「損してる？」系の生活密着ネタ
# ✅ Yahoo!コメント欄が荒れる共感・炎上系
# ✅ 「知らないと損する」系の制度・ルール変更
# ✅ 「えっ、そんなに？」という驚きの数字ネタ
# ❌ 投資専門用語が多い硬いニュース（除外）
# ❌ 副業紹介・副業おすすめ系（除外）
NEWS_QUERIES = [
    # 【最強バズ】芸能人・有名人 × お金
    {"query": "芸能人 遺産 相続 破産 資産 億円", "label": "芸能人×お金"},
    {"query": "有名人 借金 節税 脱税 資産公開", "label": "芸能人×お金"},

    # 【共感炎上】働き方・退職・会社
    {"query": "退職代行 新入社員 初日 早期退職 入社", "label": "退職・働き方"},
    {"query": "ブラック企業 残業 パワハラ 給料未払い", "label": "退職・働き方"},

    # 【生活直撃】知らないと損する制度・ルール変更
    {"query": "4月から変わる 制度変更 値上げ 廃止 改正", "label": "制度・ルール変更"},
    {"query": "保険料 税金 手取り 天引き 増税 負担増", "label": "税金・手取り"},

    # 【驚きの数字】「えっそんなに？」系
    {"query": "平均貯蓄 平均年収 老後資金 2000万円 格差", "label": "お金の格差・実態"},
    {"query": "物価上昇 値上げ 家計 食費 電気代 ガス代", "label": "物価・生活費"},

    # 【ぼったくり・損してる系】
    {"query": "損してる 知らないと損 やめたほうがいい 無駄 節約", "label": "節約・お得情報"},

    # 【投資接続】株クラへの橋渡し（やわらかめ）
    {"query": "NISA 始め方 初心者 失敗 後悔 やってみた", "label": "NISA・投資入門"},

    # 【テクノロジー】AI・ガジェット・IT系
    {"query": "AI 人工知能 ChatGPT 生成AI 新サービス 発表", "label": "テクノロジー"},
    {"query": "スマホ アプリ ガジェット 新製品 発売 テスラ EV", "label": "テクノロジー"},

    # 【経済】マクロ経済・企業ニュース
    {"query": "金利 円安 株価 日銀 経済 景気 倒産", "label": "経済"},
    {"query": "企業 決算 リストラ 解雇 上場 M&A 業績", "label": "経済"},

    # 【エンタメ×お金】話題の芸能ニュース
    {"query": "ドラマ 映画 アニメ 話題 Netflix 配信 主演", "label": "エンタメ"},
    {"query": "芸能人 結婚 離婚 引退 復帰 スキャンダル", "label": "エンタメ"},
]

# =====================================================
# Google トレンド（日本）取得 + 株クラ向けAIフィルタリング
# =====================================================
def fetch_google_trends():
    """Google Trends RSS（日本）からリアルタイムトレンドを取得"""
    import urllib.parse

    trends = []
    seen = set()

    url = 'https://trends.google.co.jp/trending/rss?geo=JP'
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            keyword = entry.get('title', '').strip()
            traffic = entry.get('ht_approx_traffic', '')
            news_title = entry.get('ht_news_item_title', '')
            news_url = entry.get('ht_news_item_url', '')
            if keyword and keyword not in seen:
                seen.add(keyword)
                trends.append({
                    'keyword': keyword,
                    'traffic': traffic,
                    'news_title': news_title,
                    'news_url': news_url,
                    'x_search_url': f"https://x.com/search?q={urllib.parse.quote(keyword)}&src=typed_query&f=top"
                })
    except Exception as e:
        print(f"[WARN] Googleトレンド取得エラー: {e}")

    return trends


def filter_trends_for_kabukura(trends, max_count=10):
    """
    AIを使ってGoogleトレンドから株クラ・お金系に関連するものだけを抽出。
    関連ニュースがない日は「本日の株クラ関連トレンドはありませんでした」と返す。
    """
    if not trends:
        return []

    trends_text = "\n".join(
        [f"{i+1}. キーワード:「{t['keyword']}」 関連ニュース:「{t['news_title'][:40] if t['news_title'] else 'なし'}」"
         for i, t in enumerate(trends)]
    )

    prompt = f"""あなたは株クラ初心者向けSNSアカウントの編集者です。

以下のGoogleトレンド（日本）のキーワード一覧から、
**株クラ初心者・お金に興味がある一般人が「おっ！」と反応しそうなもの**だけを選んでください。

【選ぶべきキーワードの基準】
✅ お金・税金・保険・年金・給料・手取り・節税・相続
✅ 株・投資・NISA・仮想通貨・為替・円安・物価
✅ 値上げ・家計・生活費・電気代・食費
✅ 退職・転職・ブラック企業・副業（紹介ではなく話題として）
✅ 有名企業の倒産・リストラ・業績悪化
✅ 芸能人・著名人 × お金（遺産・破産・節税・高額収入）
✅ 経済政策・増税・補助金・給付金

【除外するキーワード】
❌ スポーツ選手・試合結果（お金と無関係なもの）
❌ 芸能ゴシップ（お金と無関係なもの）
❌ 事件・事故・災害（お金と無関係なもの）
❌ アニメ・ゲーム・音楽（お金と無関係なもの）

【出力形式】
選んだキーワードのIDをJSON配列で返してください。
例: {{"selected_ids": [1, 3, 7]}}
関連するものが1つもない場合は {{"selected_ids": []}} を返してください。

Googleトレンド一覧:
{trends_text}

JSONのみ返答してください。"""

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = response.choices[0].message.content.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            selected_ids = result.get("selected_ids", [])
            filtered = [trends[i-1] for i in selected_ids if 1 <= i <= len(trends)]
            return filtered[:max_count]
    except Exception as e:
        print(f"[WARN] トレンドフィルタリングエラー: {e}")

    return []


# =====================================================
# Google News RSS からニュースを取得
# =====================================================
def fetch_news(queries, max_per_query=8):
    """Google News RSSからニュースを取得。
    前日（JST）以降〜当日のニュースのみを取得する。"""
    import urllib.parse
    import email.utils

    # JST基準で前日の日付を計算（前日0時以降のみ取得）
    jst = datetime.timezone(datetime.timedelta(hours=9))
    now_jst = datetime.datetime.now(jst)
    yesterday_jst = (now_jst - datetime.timedelta(days=1)).date()
    after_date_1d = yesterday_jst.strftime("%Y-%m-%d")   # 前日以降
    cutoff_1d = datetime.datetime.combine(yesterday_jst, datetime.time.min).replace(tzinfo=jst)

    all_news = []
    seen_titles = set()

    def fetch_for_query(q, after_date, cutoff_dt):
        """1つのクエリで記事を取得してリストで返す（前日・当日のみ）"""
        query_with_date = f"{q['query']} after:{after_date}"
        encoded = urllib.parse.quote(query_with_date)
        url = f"https://news.google.com/rss/search?q={encoded}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
        results = []
        for entry in feed.entries:
            title = entry.get("title", "").strip()
            if not title:
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

    for q in queries:
        # 前日・当日のニュースのみ取得
        results = fetch_for_query(q, after_date_1d, cutoff_1d)
        if not results:
            print(f"  [INFO] {q['label']}: 前日以降の記事なし（スキップ）")

        for r in results:
            if r["key"] not in seen_titles:
                seen_titles.add(r["key"])
                all_news.append({k: v for k, v in r.items() if k != "key"})

    return all_news

# =====================================================
# AIによるニュース選定・要約・フック文生成（v3最適化）
# =====================================================
def ai_select_and_summarize(news_list, target_count=10, trends=None):
    """GPTでニュース選定・要約・フック文生成（v3: 一般人向けお金ネタ最適化）"""

    news_json = json.dumps(
        [{"id": i, "title": n["title"], "label": n["label"], "source": n["source"]}
         for i, n in enumerate(news_list)],
        ensure_ascii=False
    )

    trends_str = ""
    if trends:
        trends_str = "\n\n【本日のGoogleトレンド（日本）TOP】\n"
        for t in trends[:10]:
            trends_str += f"・{t['keyword']} [{t['traffic']}]"
            if t['news_title']:
                trends_str += f" → {t['news_title'][:40]}"
            trends_str += "\n"
        trends_str += "\n※ トレンドキーワードと関連するニュースがあれば優先的に選定してください。"

    prompt = f"""あなたはXで「株クラ初心者向けお金アカウント」を運営するプロのSNSマーケターです。

【アカウントの読者層】
- 20〜40代の会社員・主婦・フリーター
- 投資初心者〜入門レベル
- 「お金の不安はあるけど投資はよくわからない」という人たち
- 難しい投資用語より「生活に直結するお金の話」に反応する

【理想のニュースの粒度（参考例）】
✅ 「中山美穂さんの遺産20億円、息子が相続放棄→相続税55%で11億円の納税地獄」
  → 芸能人ネタ × 具体的な数字 × 「自分ごと」として感じられる制度批判
✅ 「新入社員が入社初日に退職代行を依頼→コメント5000件超のバズ」
  → 「わかる！」という共感 × 炎上 × 働き方への疑問
✅ 「タイヤのパンク修理15万円→JAFならタダだった」
  → 「知らないと損する」 × 驚きの数字 × 生活密着

❌ 避けるべきニュース（硬すぎる・専門的すぎる）
  - 「日銀が利上げを検討」「FRBの金融政策」「長期金利2.4%」
  - 「オルカンとS&P500の比較」（初心者には難しすぎる）
  - 「副業のやり方・副業紹介・副業おすすめ」（絶対除外）

【選定の優先順位】
1. 芸能人・有名人 × お金（遺産・破産・資産・節税・脱税）
2. 「えっそんなに？」という驚きの数字（平均貯蓄・格差・損した金額）
3. 「知らないと損する」制度変更・ルール変更（4月から変わること等）
4. 共感・炎上系の働き方ニュース（退職代行・ブラック企業・給料未払い）
5. 生活直撃の物価・値上げ（食費・電気代・具体的な品目）
6. NISA・投資入門（やわらかい切り口のもの限定）
7. テクノロジー（AIや新製品が生活・お金に与える影響）
8. 経済（株価・金利・企業倒産など一般人にも影響するもの）
9. エンタメ（話題のドラマ・映画・芸能人ニュース）

【カテゴリバランス】
10本の中に以下のカテゴリを必ず1本以上含めること：
- テクノロジー（AI・ガジェット・IT）
- 経済（株価・金利・企業）
- エンタメ（ドラマ・映画・芸能）

【実際にバズった投稿の実例（必ずこれらの文体・構造を参考にすること）】

実例1（247.3万インプレッション）:
「三菱商事に就職した同期が、飲み会の幹事でアサヒビール出すお店選んじゃってめちゃくちゃ怒られたって言ってた。数年前の話だけど流石にこれで降格、減給は無いよね？」
→ 構造：身近な実話（固有名詞あり）＋日常の理不尽あるある＋「〜よね？」で問いかけ終わり

実例2（621.9万インプレッション）:
「リボ払いだけは絶対したらあかんってみんな言うけどさ、スマホとかの分割払いは別にいいん？後から払うならリボと同じじゃない？分割との違いってなに？？？」
→ 構造：「みんな言うけど」で逆張り＋自分の素朴な疑問＋「？？？」で終わる賛否型

実例3（176.7万インプレッション）:
「ご近所さんに証券会社勤めの旦那さんおるんやけど夫婦揃ってNISA使ってないらしい。証券会社勤めってNISAしたらあかん決まりあったっけ？」
→ 構造：身近な実話（具体的な職業）＋「〜あったっけ？」で素直な疑問形終わり

実例4（146.1万インプレッション）:
「NISAのリスクって「暴落して一文無しになること」よりも、コツコツ切り詰めて積立投資してきた結果「若い頃に散財してた人より年金少なくていいよな？」って後出しで言われる可能性のほうが高い気してる。」
→ 構造：「〜よりも〜の方が高い気してる」という逆張り視点＋共感を誘う不安の言語化

実例5（109万インプレッション）:
「年金ってなんで払った額以下しか貰われへんの？？厚生年金は会社も払ってんのに謎。自分で残りの40年資産運用した方がよっぽどお金増えると思うんやけど...国って国民にはNISA勧めるくせに運用下手すぎん？？？？？」
→ 構造：「なんで〜の？？」という怒りの疑問＋「〜すぎん？？？」で感情的に締める

【バズ投稿から抽出した共通ルール】
✅ 話し言葉・関西弁・砕けた表現を使う（「〜やけど」「〜あかん」「〜やん」「〜よね？」）
✅ 「〜よね？」「〜あったっけ？」「〜なに？？？」など疑問形で終わるとリプが増える
✅ 固有名詞（三菱商事・証券会社・NISA・リボ払い）を入れるとリアリティが出る
✅ 「みんな言うけど」「〜って言われてるけど」で逆張りするとバズりやすい
✅ 「？？？」「？？？？？」など疑問符を複数重ねると感情が伝わる
✅ 難しい投資用語は一切使わない。中学生でも理解できる言葉で書く
✅ 1ツイートで完結する（スレッドにしない）
❌ 「〜です」「〜ます」などの丁寧語は使わない（距離感が出る）
❌ 「投資をしましょう」「資産形成が大切です」などの説教口調は絶対NG
❌ 「#NISA #投資 #資産運用」などのハッシュタグは入れない

【投稿文3パターンの定義（上記実例の文体で生成すること）】
各ニュースに対して以下の3パターンの投稿文を生成してください。

■ パターンA「身近な実話・共感型」（実例1・3を参考）
- 「〇〇に勤めてる友達が〜」「ご近所の〇〇さんが〜」など身近な実話風に始める
- 固有名詞（職業・企業名・制度名）を入れてリアリティを出す
- 最後は「〜よね？」「〜あったっけ？」など素朴な疑問形で終わる
- 話し言葉・砕けた表現で書く
- 140字以内

■ パターンB「逆張り・賛否型」（実例2・4を参考）
- 「〇〇ってみんな言うけどさ」「〜よりも〜の方が怖い気してる」など逆張りで始める
- 「え、それって〜と同じじゃない？」という素朴な疑問・矛盾の指摘を入れる
- 「？？？」「？？？？？」で感情的に締める
- 話し言葉・砕けた表現で書く
- 140字以内

■ パターンC「怒り・問いかけ型」（実例5を参考）
- 「なんで〜の？？」「〜すぎん？？？？？」など怒りや驚きの感情から始める
- 「国って〜」「会社って〜」「銀行って〜」など制度・組織への不満を言語化する
- 具体的な数字（金額・年数・割合）を必ず1つ入れる
- 「〜すぎん？？？？？」で感情的に締める
- 話し言葉・砕けた表現で書く
- 140字以内

以下のニュースリストから最もバズりやすい{target_count}本を選び、
各ニュースについて以下のJSON形式で回答してください：

{{
  "selected": [
    {{
      "id": <元のid>,
      "summary": "<一般人でも一瞬で理解できる一言要約（40字以内）>",
      "hook": "<Xでそのまま使えるフック文（60字以内）。「えっ！」「知らなかった」「これは怒る」という感情を引き出す言葉で>",
      "buzz_reason": "<なぜ一般人にバズるかの理由（30字以内）>",
      "search_keyword": "<Xで検索するキーワード（10字以内）>",
      "post_a": "<パターンA: 共感ストーリー型（140字以内）。「私も〇〇だった」から始める共感型>",
      "post_b": "<パターンB: 賛否・炎上型（140字以内）。強い呼びかけ＋断言で締める炎上型>",
      "post_c": "<パターンC: 問いかけ・リプ狙い型（140字以内）。驚きの数字＋疑問形で締めるリプ狙い型>",
      "score": <バズりやすさスコア 1-10>
    }}
  ]
}}

ニュースリスト:
{news_json}
{trends_str}

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
# Markdownレポートの生成
# =====================================================
def generate_report(news_list, selected_items, date_str, trends=None):
    """Markdownレポートを生成"""

    lines = []
    lines.append(f"# 📊 株クラ朝刊 ── {date_str}")
    lines.append("")
    lines.append("> **毎朝8時配信｜株クラ初心者向けトレンドニュース10選**")
    lines.append("> お金・働き方・投資の「今日の話題」をまとめました。Xの発信ネタにご活用ください。")
    lines.append("")

    if trends:
        lines.append("## 🔥 本日の株クラ注目トレンド（Googleトレンド・お金系厳選）")
        lines.append("")
        lines.append("> お金・投資・働き方・生活費に関連するトレンドキーワードのみを抽出しています。")
        lines.append("")
        lines.append("| # | トレンドキーワード | 検索数 | 関連ニュース |")
        lines.append("|:---:|:---|:---:|:---|")
        for i, t in enumerate(trends[:10], 1):
            news_link = f"[{t['news_title'][:25]}...]({t['news_url']})" if t['news_title'] and t['news_url'] else t['news_title'][:25] if t['news_title'] else '-'
            x_link = f"[X検索]({t['x_search_url']})"
            lines.append(f"| {i} | **{t['keyword']}** {x_link} | {t['traffic']} | {news_link} |")
        lines.append("")
        lines.append("---")
        lines.append("")
    else:
        lines.append("## 🔥 本日の株クラ注目トレンド")
        lines.append("")
        lines.append("> 本日のGoogleトレンドにお金・投資関連のキーワードはありませんでした。")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("---")
    lines.append("")

    for rank, item in enumerate(selected_items, 1):
        news = news_list[item["id"]]
        keyword = item.get("search_keyword", "")
        encoded_kw = keyword.replace(" ", "%20")

        lines.append(f"## {rank}. [{news['label']}] {news['title']}")
        lines.append("")
        lines.append("| 項目 | 内容 |")
        lines.append("|------|------|")
        lines.append(f"| **一言要約** | {item['summary']} |")
        lines.append(f"| **Xフック文** | {item['hook']} |")
        lines.append(f"| **バズる理由** | {item['buzz_reason']} |")
        lines.append(f"| **バズスコア** | {'⭐' * item.get('score', 5)} ({item.get('score', 5)}/10) |")
        lines.append(f"| **情報源** | {news['source']}（{news['published'][:16] if news['published'] else ''}） |")
        lines.append("")
        post_a = item.get('post_a', item.get('post_template', ''))
        post_b = item.get('post_b', '')
        post_c = item.get('post_c', '')

        lines.append("📝 **投稿候補3パターン**")
        lines.append("")
        lines.append("> **【パターンA】共感ストーリー型** — 「私も〇〇だった」から始める共感型**")
        lines.append(f"> {post_a}")
        lines.append("")
        lines.append("> **【パターンB】賛否・炎上型** — 強い呼びかけ・断言で締める炎上型**")
        lines.append(f"> {post_b}")
        lines.append("")
        lines.append("> **【パターンC】問いかけ・リプ狙い型** — 驚きの数字・疑問形で締めるリプ狙い型**")
        lines.append(f"> {post_c}")
        lines.append("")
        lines.append(f"🔗 **ニュース原文**: [{news['title'][:40]}...]({news['link']})")
        lines.append("")
        lines.append(f"🐦 **Xバズ投稿を探す**: [「{keyword}」で検索 →](https://x.com/search?q={encoded_kw}&src=typed_query&f=top)")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("## 📌 本日のまとめ")
    lines.append("")
    lines.append("本日のニュース10本をピックアップしました。")
    lines.append("**投稿テンプレート**をそのまま使うか、自分の言葉でアレンジしてポストしてみてください。")
    lines.append("")
    lines.append("**バズ投稿を作る3つのコツ**")
    lines.append("")
    lines.append("1. **冒頭に「私も〇〇だった」という共感ストーリー**を入れると伸びやすい")
    lines.append("2. **具体的な数字**（〇〇円、〇〇%、〇〇万人）を使うとリアリティが増す")
    lines.append("3. **最後に「あなたはどう思いますか？」**と問いかけると返信が増える")
    lines.append("")
    lines.append("---")
    lines.append(f"*このレポートは自動生成されました。投資は自己責任でお願いします。*")
    lines.append(f"*生成日時: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(lines)

# =====================================================
# LINE Notifyへの送信
# =====================================================
def send_to_line(report_md, date_str, token, date_file=None):
    """LINE Messaging APIでグループにレポートを送信（URLリンク付き）"""
    import requests as req_lib

    access_token = LINE_CHANNEL_ACCESS_TOKEN
    group_id = LINE_GROUP_ID

    if not access_token or not group_id:
        print("[SKIP] LINE_CHANNEL_ACCESS_TOKEN または LINE_GROUP_ID が設定されていないため、LINE送信をスキップします")
        return False

    # 朝刊WebページのURL
    if date_file:
        page_url = f"{WEB_BASE_URL}/{date_file}"
    else:
        page_url = WEB_BASE_URL

    # ニュースTOP10のサマリーを作成（LINEメッセージ用）
    lines = report_md.split("\n")
    header = f"📊 株クラ朝刊 {date_str}\n"
    header += "━" * 22 + "\n"
    news_summary = ""
    rank = 0
    for i, line in enumerate(lines):
        if line.startswith("## ") and ". [" in line:
            rank += 1
            match = re.search(r'\[(.+?)\] (.+)', line)
            if match:
                category = match.group(1)
                title = match.group(2)[:28]
                news_summary += f"\n{rank}. 【{category}】\n{title}...\n"
        if "**Xフック文**" in line and rank <= 5:
            hook = line.replace("| **Xフック文** | ", "").replace(" |", "").strip()
            if len(hook) > 50:
                hook = hook[:50] + "..."
            news_summary += f"💬 {hook}\n"
    footer = (
        "\n" + "━" * 22 + "\n"
        f"📱 今日の朝刊（全文・投稿テンプレ付き）\n"
        f"👇 タップして確認\n"
        f"{page_url}"
    )
    full_message = header + news_summary + footer
    # 5000文字制限に収める
    if len(full_message) > 4900:
        full_message = full_message[:4900] + "..."
    api_url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }
    data = {
        "to": group_id,
        "messages": [{"type": "text", "text": full_message}]
    }
    try:
        res = req_lib.post(api_url, headers=headers, json=data)
        if res.status_code == 200:
            print(f"[OK] LINE Messaging API送信成功")
            print(f"[OK] 朝刊URL: {page_url}")
            return True
        else:
            print(f"[ERROR] LINE送信失敗: {res.status_code} {res.text}")
            return False
    except Exception as e:
        print(f"[ERROR] LINE送信エラー: {e}")
        return False

# =====================================================
# メイン処理
# =====================================================
def main():
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))  # JST
    date_str = now.strftime("%Y年%m月%d日（%a）").replace(
        "Mon", "月").replace("Tue", "火").replace("Wed", "水").replace(
        "Thu", "木").replace("Fri", "金").replace("Sat", "土").replace("Sun", "日")
    date_file = now.strftime("%Y%m%d")

    print(f"[{now.strftime('%H:%M:%S')}] Googleトレンド取得中...")
    all_trends = fetch_google_trends()
    print(f"  → {len(all_trends)}件のトレンドを取得: {', '.join([t['keyword'] for t in all_trends[:5]])}...")
    print(f"[{now.strftime('%H:%M:%S')}] 株クラ向けトレンドをAIフィルタリング中...")
    trends = filter_trends_for_kabukura(all_trends, max_count=10)
    if trends:
        print(f"  → {len(trends)}件の株クラ関連トレンドを抽出: {', '.join([t['keyword'] for t in trends])}")
    else:
        print(f"  → 本日は株クラ関連トレンドなし（全トレンドを非表示）")

    print(f"[{now.strftime('%H:%M:%S')}] ニュース収集開始...")
    news_list = fetch_news(NEWS_QUERIES, max_per_query=8)
    print(f"  → {len(news_list)}件のニュースを収集")

    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] AI選定・要約・テンプレート生成中...")
    selected = ai_select_and_summarize(news_list, target_count=10, trends=trends)
    print(f"  → {len(selected)}件のニュースを選定")

    selected.sort(key=lambda x: x.get("score", 0), reverse=True)

    report = generate_report(news_list, selected, date_str, trends=trends)

    output_path = os.path.join(OUTPUT_DIR, f"kabukura_news_{date_file}.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] レポート保存完了: {output_path}")

    if LINE_CHANNEL_ACCESS_TOKEN and LINE_GROUP_ID:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] LINE Messaging API送信中...")
        send_to_line(report, date_str, None, date_file=date_file)
    else:
        print(f"[INFO] LINE_CHANNEL_ACCESS_TOKEN または LINE_GROUP_ID 未設定のため送信スキップ")

    print("=" * 50)
    print(f"  出力ファイル: {output_path}")
    print(f"  ニュース件数: {len(selected)}件")
    print("=" * 50)

if __name__ == "__main__":
    main()
