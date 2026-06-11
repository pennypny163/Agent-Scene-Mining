# 数据源清单与配置指南（项目最值钱的资产）

> 脚本是死的，源是活的。源选得好，库的质量就赢了一半。
> 配置文件：`data/sources.json`（脚本读它）。本文档讲**怎么拿、怎么验证、怎么扩展**每一类源。

---

## 总览：五类源，难度递增

| 类别 | 拿法 | 难度 | 燃料质量 |
| --- | --- | --- | --- |
| YouTube 频道 | 原生 RSS，免费无需 key | 🟢 极易 | 高（实操玩法多） |
| Newsletter | Substack/Beehiiv 自带 RSS | 🟢 极易 | 极高（精选过的玩法） |
| 技术博客/聚合 | 官方 RSS | 🟢 易 | 高（首发地） |
| RSSHub 中文社区 | RSSHub 转换（即刻/36氪/知乎等） | 🟡 建议自建 | 中高（中文玩法） |
| 微信公众号 | RSSHub / WeWe RSS 中转 | 🔴 需部署 | 高（中文优质源） |

核心策略：**🟢 三类先全自动跑起来，🟡🔴 中文源用 RSSHub/中转 + 人工投喂补齐。**

---

## 一、YouTube 频道 RSS（最简单，先做这个）

### 原理
YouTube 每个频道都有一个**原生 RSS**，完全免费、无需 API key、无限额：

```
https://www.youtube.com/feeds/videos.xml?channel_id=频道ID
```

例：Matt Wolfe →
`https://www.youtube.com/feeds/videos.xml?channel_id=UChpleBmo18P08aKCIgti38g`

### 如何拿到任意频道的 channel_id（3 种方法）

1. **最简单**：频道主页 URL 若是 `youtube.com/channel/UCxxxx`，那串 `UCxxxx` 就是。
2. **看源码**：频道页右键「查看网页源代码」，搜 `channelId`，后面的值就是。
3. **在线工具**：搜 "youtube channel id finder"，粘贴频道链接即可。

### 已为你验证的核心频道（已写入 sources.json）
Matt Wolfe、AI Explained、AI Jason、Sam Witteveen、The AI Advantage、All About AI、Prompt Engineering、WorldofAI —— 都是**实操/工具/Agent 玩法**导向，正好喂你的"场景库"。

### 验证一个 RSS 是否有效
```bash
curl -sL "https://www.youtube.com/feeds/videos.xml?channel_id=UChpleBmo18P08aKCIgti38g" | head -40
# 能看到 <entry> 节点即有效
```

---

## 二、Newsletter RSS（质量最高，强烈推荐）

### 为什么这是最优燃料
Newsletter（The Rundown、Latent Space、One Useful Thing…）是**人工精选过的**内容——作者已经帮你筛掉噪声。比原始社交媒体信噪比高得多。

### 两种拿法
- **方法 A（推荐）直接抓 RSS**：大多数 Substack/Beehiiv 都有 RSS，免去收邮件解析。已写入 sources.json。
  - Substack 通用规律：`https://<名字>.substack.com/feed`
- **方法 B 收邮件解析**：少数只发邮件不开 RSS 的，用一个专用邮箱订阅，定时拉取解析。你的 QQ 邮箱可以专门干这个。

### 已为你验证的核心 newsletter
| 名称 | RSS | 看点 |
| --- | --- | --- |
| The Rundown AI | `https://rss.beehiiv.com/feeds/2R3C6Bt5wj.xml` | 每日要闻+工具，玩法密集 |
| Latent Space | `https://www.latent.space/feed` | 工程/Agent 深度 |
| One Useful Thing | `https://www.oneusefulthing.org/feed` | Ethan Mollick 的实操玩法 |
| Ahead of AI | `https://magazine.sebastianraschka.com/feed` | 技术深度 |
| Last Week in AI | `https://lastweekin.ai/feed` | 周报 |
| Unwind AI | `https://unwindai.substack.com/feed` | 工具/Agent 教程 |

---

## 三、技术博客 / 聚合 RSS

新玩法、新工具的首发地：

| 名称 | RSS | 看点 |
| --- | --- | --- |
| Hacker News (AI agent) | `https://hn.algolia.com/api/v1/search_by_date?query=AI%20agent&tags=story` | 社区热议，官方搜索 API 最稳 |
| Product Hunt | `https://www.producthunt.com/feed` | 新 AI 产品首发 |
| Simon Willison | `https://simonwillison.net/atom/everything/` | 顶级实操博主 |
| LangChain Blog | `https://blog.langchain.dev/rss/` | Agent 框架动态 |

> 提示：HN 优先用 Algolia 官方搜索 API（`search_by_date?query=...&tags=story`），完全免费、无需 key、命中量大且实时；`hnrss.org/newest?q=` 作为备路（偶发限流返回空）。把 `query=` 换成 `LLM`、`Claude` 等可开多条线。

---

## 四、RSSHub（强制把任意网站转成 RSS，补齐中文社区源）

### 它解决什么
原生 RSS 只能订阅"网站愿意开放"的内容。**RSSHub 能把不提供 RSS 的网站强制转成 RSS**——即刻、36氪、知乎、B站、少数派、公众号都能转。这是补齐中文源的关键工具。

### 配置位置
`sources.json` 的 `rsshub` 块。`base` + 每条 `path` 拼接成完整 URL：
```
base = https://rsshub.app
path = /sspai/tag/AI
→ 完整 URL = https://rsshub.app/sspai/tag/AI
```

### 已为你预置的路由（已写入 sources.json，默认 enabled=false）
| 名称 | 路由 path | 看点 |
| --- | --- | --- |
| 即刻·AI话题 | `/jike/topic/text/:id` | 中文 AI 玩法分享 |
| 36氪·AI | `/36kr/search/articles/AI` | AI 产业/产品 |
| 知乎·AI热榜 | `/zhihu/hotlist` | 热议话题 |
| 少数派·AI标签 | `/sspai/tag/AI` | 工具实操/玩法 |
| GitHub Trending | `/github/trending/daily/any` | 开源趋势 |

> 路由怎么找：① 查官方文档 `docs.rsshub.app`；② 装浏览器扩展 **RSSHub Radar**，打开任意页面自动提示可用路由。

### ⚠️ 免费但不稳 —— 务必自建
官方公网实例 `https://rsshub.app` 经常限流/超时，公众号等热门路由还常失效。**长期使用强烈建议自建：**

```bash
# 一行命令起一个本地 RSSHub
docker run -d --name rsshub -p 1200:1200 diygod/rsshub
# 起来后把 sources.json 的 base 改成 http://你的IP:1200
curl "http://localhost:1200/sspai/tag/AI"   # 验证
```

自建后：稳定性大幅提升、不受公网限流、可配代理抓墙内外。把 `rsshub.base` 换成自己的地址，再把要用的源 `enabled` 改 `true` 即可。

---

## 五、微信公众号 RSS（中文核心，需中转）

这是唯一需要动手搭的一环。公众号没有官方 API，三条路：

| 方案 | 原理 | 优缺点 | 推荐度 |
| --- | --- | --- | --- |
| **RSSHub** | 上面那套，含 `/wechat` 路由 | 免费，但公众号路由最不稳、易失效 | ⭐⭐ 先试 |
| **WeWe RSS** | 基于微信读书，自建 Docker | 稳定，需一台服务器 + 一点配置 | ⭐⭐⭐ 长期 |
| 自建爬虫(搜狗) | 搜狗微信搜索抓取 | 门槛高、易封 | ❌ 不推荐 |

### 推荐策略
**先用 RSSHub 覆盖能覆盖的核心号，跑通后再考虑 WeWe RSS 自建提升稳定性。**

### 目标公众号（已写入 sources.json，待填 url）
量子位(QbitAI)、机器之心(almosthuman2014)、新智元(AI_era)、Founder Park、AI 产品黄叔等。

### WeWe RSS 自建简要步骤（长期方案）
1. 一台云服务器（腾讯云/阿里云均可），装 Docker
2. 拉起 WeWe RSS 容器（开源项目，基于微信读书登录）
3. Web 界面里「添加」公众号链接 → 自动识别 → 生成 RSS
4. 点该号右上角「RSS」拿到订阅地址，URL 后加 `?limit=20` 拿全量
5. 把地址填进 `sources.json` 的 `wechat_rss.feeds[].url`，并把 `enabled` 改 true

> ⚠️ 这一步是整个项目唯一需要常驻服务器的地方。若你想保持"零运维"，可暂时跳过公众号自动化，用下面的「人工投喂」补中文。

---

## 六、人工投喂（绕开中文反爬的杀手锏）

不和小红书反爬硬刚。你刷到好的玩法（小红书/任意链接），把链接丢进 `sources.json` 的 `manual_feed.pending` 数组，脚本下次跑时自动抓取正文 → LLM 抽成场景 → 入库。

```json
"manual_feed": {
  "pending": [
    "https://www.xiaohongshu.com/xxxxx",
    "https://mp.weixin.qq.com/s/xxxxx"
  ]
}
```

**"人工发现 + AI 加工"——这是这个产品真正的甜区：保留人对优质内容的判断力，把最烦的整理工作自动化。**

---

## 七、源管理原则

1. **质量 > 数量**：宁可 15 个精源，不要 60 个噪声源。`enabled` 字段控制开关，先开高质量的。
2. **中英搭配**：英文源拿一手玩法，中文源拿本土化场景。
3. **定期体检**：RSS 会失效。脚本应记录每个源的"上次成功抓取时间"，连续失败的标记下线。
4. **关键词演进**：HN 的关键词、订阅的频道，应随赛道热点季度性调整。

---

## 八、合规提醒

- RSS / 官方 API / 邮件订阅 = ✅ 内容方主动提供的合规通道，放心用。
- 模拟登录爬小红书/公众号 = ⚠️ 有封号与法律风险，本项目不走这条路。
- 抓取频率克制（每日一次足够），尊重各源的 robots 与限流。

---

*这份清单是活的，随用随补。下一步：抓取脚本 `scripts/crawl.py` 会读取 `data/sources.json` 逐源抓取。*
