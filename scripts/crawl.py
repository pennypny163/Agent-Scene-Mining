#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
crawl.py — AI Agent 新场景动态追踪库 · 抓取处理主脚本

流水线：
  1. fetch       读 sources.json，逐源抓原始条目
  2. pre_filter  关键词命中 + 链接去重 + 时间窗（先于 LLM，省钱）
  3. extract     DeepSeek 判别"场景 vs 资讯" + 抽 9 字段（核心）
  4. dedupe      语义去重，同一玩法合并、提及次数 +1
  5. score       热度 = 提及次数 × 源权重 + 新颖度
  6. write       增量写入 data/scenes.json

用法：
  python crawl.py            # 正常跑（需 DEEPSEEK_API_KEY）
  python crawl.py --mock     # 干跑，不调 LLM，用规则桩，验证全链路
  python crawl.py --limit 20 # 每源最多处理 N 条（调试用）
"""

import os
import re
import sys
import json
import time
import argparse
import hashlib
import datetime
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_PATH = os.path.join(ROOT, "data", "sources.json")
SCENES_PATH = os.path.join(ROOT, "data", "scenes.json")

# ---------- 可调参数（也可由 sources.json / env 覆盖）----------
HEAT_THRESHOLD = int(os.environ.get("HEAT_THRESHOLD", "50"))   # 入库门槛（宽松起步）
TIME_WINDOW_DAYS = int(os.environ.get("TIME_WINDOW_DAYS", "14"))  # 只看近 N 天
PER_SOURCE_LIMIT = 25
# 粗筛关键词：命中任一即通过（中英）。可按赛道演进调整。
KEYWORDS = [
    "agent", "ai ", "llm", "gpt", "claude", "cursor", "mcp", "rag",
    "workflow", "automation", "prompt", "copilot", "chatbot",
    "智能体", "大模型", "提示词", "自动化", "工作流", "助手", "智能",
]
# 源权重：用于热度计算，权威/精选源权重更高
SOURCE_WEIGHT = {
    "newsletter_rss": 1.3, "tech_blog_rss": 1.2,
    "youtube": 1.0, "rsshub": 0.9, "wechat_rss": 1.1, "manual_feed": 1.4,
}
UA = "Mozilla/5.0 (compatible; AISceneCrawler/2.0; +https://github.com)"


# ============== 工具函数 ==============
def log(msg):
    print("[crawl] " + str(msg), flush=True)


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def today():
    return datetime.date.today().isoformat()


def make_id(text):
    return "s" + hashlib.md5(text.encode("utf-8")).hexdigest()[:10]


def normalize(text):
    """归一化：去标点、转小写、压空白，用于去重比对。"""
    text = re.sub(r"[\s\W_]+", "", (text or "").lower())
    return text


# ============== 1. fetch ==============
def parse_rss(xml_text):
    """解析 RSS/Atom，返回 [{title, link, summary, published}]"""
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    # RSS 2.0
    for it in root.iter("item"):
        items.append({
            "title": (it.findtext("title") or "").strip(),
            "link": (it.findtext("link") or "").strip(),
            "summary": (it.findtext("description") or "").strip(),
            "published": (it.findtext("pubDate") or "").strip(),
        })
    # Atom
    ns = "{http://www.w3.org/2005/Atom}"
    for it in root.iter(ns + "entry"):
        link_el = it.find(ns + "link")
        link = link_el.get("href") if link_el is not None else ""
        items.append({
            "title": (it.findtext(ns + "title") or "").strip(),
            "link": link,
            "summary": (it.findtext(ns + "summary") or it.findtext(ns + "content") or "").strip(),
            "published": (it.findtext(ns + "published") or it.findtext(ns + "updated") or "").strip(),
        })
    return items


def fetch_hn_algolia(url):
    """HN Algolia JSON API → 统一条目格式"""
    items = []
    try:
        data = json.loads(http_get(url))
        for h in data.get("hits", []):
            items.append({
                "title": h.get("title") or h.get("story_title") or "",
                "link": h.get("url") or ("https://news.ycombinator.com/item?id=" + str(h.get("objectID", ""))),
                "summary": h.get("story_text") or "",
                "published": h.get("created_at", ""),
            })
    except Exception as e:
        log("  HN Algolia 解析失败: %s" % e)
    return items


def fetch_source(feed, kind, base=""):
    """根据源类型抓取，返回统一条目 list，每条带 _source/_kind 元信息"""
    name = feed.get("name", "?")
    try:
        if kind == "youtube":
            url = "https://www.youtube.com/feeds/videos.xml?channel_id=" + feed["channel_id"]
            items = parse_rss(http_get(url))
        elif feed.get("type") == "json_api":
            items = fetch_hn_algolia(feed["url"])
            if not items and feed.get("fallback"):
                items = parse_rss(http_get(feed["fallback"]))
        elif kind == "rsshub":
            items = parse_rss(http_get(base.rstrip("/") + feed["path"]))
        else:  # newsletter_rss / tech_blog_rss / wechat_rss
            items = parse_rss(http_get(feed["url"]))
    except Exception as e:
        log("  [跳过] %s 抓取失败: %s" % (name, e))
        return []
    for it in items:
        it["_source"] = name
        it["_kind"] = kind
        it["_lang"] = feed.get("lang", "en")
    log("  %s: 拿到 %d 条" % (name, len(items)))
    return items


def fetch_all(sources, limit):
    raw = []
    for kind in ["youtube", "newsletter_rss", "tech_blog_rss", "rsshub", "wechat_rss"]:
        block = sources.get(kind)
        if not block:
            continue
        base = block.get("base", "")
        feeds = block.get("channels") or block.get("feeds") or []
        for feed in feeds:
            if not feed.get("enabled"):
                continue
            items = fetch_source(feed, kind, base)
            raw.extend(items[:limit])
            time.sleep(0.5)  # 礼貌限速
    # 人工投喂
    manual = sources.get("manual_feed", {}).get("pending", [])
    for url in manual:
        raw.append({"title": "", "link": url, "summary": "", "published": today(),
                    "_source": "人工投喂", "_kind": "manual_feed", "_lang": "zh"})
    return raw


# ============== 2. pre_filter ==============
def keyword_hit(item):
    blob = (item.get("title", "") + " " + item.get("summary", "")).lower()
    return any(k in blob for k in KEYWORDS)


def pre_filter(raw, seen_links):
    kept = []
    for it in raw:
        link = it.get("link", "")
        if link and link in seen_links:
            continue            # 已抓过
        if it["_kind"] == "manual_feed":
            kept.append(it)     # 人工投喂无条件进
            continue
        if not it.get("title"):
            continue
        if not keyword_hit(it):
            continue            # 关键词不命中
        kept.append(it)
    log("粗筛：%d → %d 条" % (len(raw), len(kept)))
    return kept


# ============== 3. extract（LLM 判别 + 抽取）==============
EXTRACT_PROMPT = """你是 AI 应用场景情报分析师。判断下面这条内容对"想用好 AI 的人"是否有【实操参考价值】。

【有价值，要收】满足任一即可：
- 介绍某个 AI 工具/产品能做什么、怎么用（含新工具发布、工具推荐）
- 某个具体用法/玩法/教程（如"用 X 做 Y"）
- 可迁移的实践经验、方法或技巧（即使是观点文，只要能指导别人动手）

【无价值，丢弃】返回 {"is_scene": false}：
- 纯融资/并购/人事/股价/榜单排名等商业新闻
- 纯行业评论、趋势预测，无任何可操作内容
- 标题党、与 AI 实操无关

有价值则返回严格 JSON：
{
  "is_scene": true,
  "name": "场景/玩法名称，一句话点题（≤25字，中文）",
  "desc": "一句话描述：能做什么、怎么用、解决什么问题（≤50字，中文）",
  "category": "从[内容创作,编程开发,办公效率,数据分析,营销增长,学习研究,生活娱乐,自动化工作流]选一个",
  "roles": ["从[产品经理,开发者,运营/营销,设计师,学生/研究,咨询/分析,创业者,通用]选1-3个"],
  "tools": "涉及的 AI 工具，逗号分隔"
}

注意：英文内容也要把 name/desc 翻译成中文。

内容：
标题：{title}
正文：{summary}

只返回 JSON，不要解释。"""

VALID_CATS = ["内容创作", "编程开发", "办公效率", "数据分析", "营销增长", "学习研究", "生活娱乐", "自动化工作流"]
VALID_ROLES = ["产品经理", "开发者", "运营/营销", "设计师", "学生/研究", "咨询/分析", "创业者", "通用"]


def call_deepseek(prompt):
    """调用 DeepSeek chat completions，返回文本。"""
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def mock_extract(item):
    """--mock 模式：用规则桩模拟 LLM，验证链路而不花钱。
    简单规则：标题含'how/教程/用.../build/搭建'等动手词→当作场景。"""
    title = item.get("title", "")
    low = title.lower()
    action_words = ["how", "build", "用", "教程", "搭建", "自动", "make", "create", "guide", "tutorial", "agent"]
    if not any(w in low for w in action_words):
        return {"is_scene": False}
    cat = "自动化工作流" if ("auto" in low or "自动" in low or "workflow" in low) else "编程开发"
    return {
        "is_scene": True,
        "name": title[:25] if title else "未命名场景",
        "desc": (item.get("summary", "")[:50] or title[:50]),
        "category": cat,
        "roles": ["开发者", "通用"],
        "tools": "AI",
    }


def parse_llm_json(text):
    """从 LLM 输出里抠出 JSON。"""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def extract(items, mock=False):
    scenes = []
    drop = 0
    for it in items:
        if mock:
            obj = mock_extract(it)
        else:
            try:
                obj = parse_llm_json(call_deepseek(
                    EXTRACT_PROMPT.replace("{title}", it.get("title", ""))
                                  .replace("{summary}", it.get("summary", "")[:1500])
                )) or {"is_scene": False}
                time.sleep(0.3)
            except Exception as e:
                log("  LLM 调用失败，跳过一条: %s" % e)
                continue
        if not obj.get("is_scene"):
            drop += 1
            continue
        # 字段清洗与兜底
        cat = obj.get("category", "")
        if cat not in VALID_CATS:
            cat = "自动化工作流"
        roles = [r for r in obj.get("roles", []) if r in VALID_ROLES] or ["通用"]
        scenes.append({
            "name": (obj.get("name") or it.get("title", ""))[:40],
            "desc": (obj.get("desc") or "")[:80],
            "category": cat,
            "roles": roles[:3],
            "tools": obj.get("tools", "AI")[:40],
            "source": it["_source"],
            "url": it.get("link", ""),
            "date": today(),
            "_mentions": 1,
            "_kind": it["_kind"],
        })
    log("抽取：%d 条 → 场景 %d 条（丢弃资讯 %d 条）" % (len(items), len(scenes), drop))
    return scenes


# ============== 4. dedupe（语义去重 + 合并）==============
def dedupe(new_scenes, existing):
    """同一玩法合并：用归一化名做 key。已存在则提及+1，否则新增。"""
    index = {}
    for s in existing:
        index[normalize(s["name"])] = s
    added, merged = 0, 0
    for s in new_scenes:
        key = normalize(s["name"])
        if key in index:
            old = index[key]
            old["_mentions"] = old.get("_mentions", 1) + 1
            merged += 1
        else:
            s["id"] = make_id(key + s["url"])
            index[key] = s
            existing.append(s)
            added += 1
    log("去重：新增 %d 条，合并(提及+1) %d 条" % (added, merged))
    return existing


# ============== 5. score ==============
def score_all(scenes):
    for s in scenes:
        mentions = s.get("_mentions", 1)
        weight = SOURCE_WEIGHT.get(s.get("_kind", ""), 1.0)
        # 新颖度：越近收录加分
        try:
            age = (datetime.date.today() - datetime.date.fromisoformat(s["date"])).days
        except Exception:
            age = 0
        freshness = max(0, 15 - age)
        base = 45 + mentions * 12 * weight + freshness
        s["heat"] = min(100, int(round(base)))
    return scenes


# ============== 6. write ==============
def load_json(path, default):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def write_scenes(data, scenes):
    # 过滤低于门槛的（但保留已有的高分历史）
    kept = [s for s in scenes if s.get("heat", 0) >= HEAT_THRESHOLD]
    kept.sort(key=lambda s: s.get("heat", 0), reverse=True)
    data["scenes"] = kept
    data.setdefault("meta", {})["updated_at"] = today()
    with open(SCENES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log("写入：scenes.json 共 %d 条（门槛 heat≥%d）" % (len(kept), HEAT_THRESHOLD))


# ============== main ==============
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mock", action="store_true", help="不调 LLM，用规则桩验证链路")
    ap.add_argument("--limit", type=int, default=PER_SOURCE_LIMIT, help="每源最多处理条数")
    args = ap.parse_args()

    log("=== 开始（mock=%s）===" % args.mock)
    sources = load_json(SOURCES_PATH, {})
    scenes_data = load_json(SCENES_PATH, {"meta": {}, "scenes": [],
        "categories": VALID_CATS, "roles": VALID_ROLES, "sources": []})
    existing = scenes_data.get("scenes", [])
    seen_links = set(s.get("url", "") for s in existing)

    raw = fetch_all(sources, args.limit)
    log("抓取合计：%d 条原始条目" % len(raw))
    candidates = pre_filter(raw, seen_links)
    new_scenes = extract(candidates, mock=args.mock)
    merged = dedupe(new_scenes, existing)
    scored = score_all(merged)
    write_scenes(scenes_data, scored)
    log("=== 完成 ===")


if __name__ == "__main__":
    main()
