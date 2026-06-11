# AI Agent 新场景动态追踪库

> Agent 自动追踪技术社区与社交媒体的 AI 新玩法，结构化沉淀，可筛选可订阅。
> 「720个Openclaw应用场景汇总」的 2.0 升级版：从人工收集的静态清单，进化为自动追踪的动态情报库。

🔗 **在线访问**：（部署后填入 GitHub Pages 地址）

## 这是什么

一个**零后端、零成本、自托管**的 AI 应用场景库。与其绑定单一工具的热度，不如绑定「AI Agent 新场景」这个持续生长的赛道——只要 AI 还在迭代，这个库就永远有新内容。

- **数据库** = 仓库里的一个 `data/scenes.json`
- **抓取器** = GitHub Actions 定时跑脚本
- **展示层** = 纯静态前端，读 JSON 渲染
- **部署** = GitHub Pages，push 即更新

## 核心特性

- 🔍 **多维筛选**：按场景分类 / 适用角色 / 数据来源 / 热度区间任意组合
- 🔃 **排序**：热度优先 / 最新优先
- 🌗 **深浅色主题**，响应式，手机可看
- ⚡ **纯静态**：无数据库、无服务器、无运维

## 数据结构

每条场景 9 个字段（与字段定义保持一致）：

| 字段 | 说明 |
| --- | --- |
| name | 场景名称（一句话点题） |
| desc | 一句话描述（怎么做、解决什么问题） |
| category | 场景分类（8 类） |
| roles | 适用角色（多值） |
| tools | 涉及的 AI 工具 |
| source | 数据来源 |
| heat | 热度评分 0-100 |
| url | 原文链接 |
| date | 收录日期 |

## 项目结构

```
ai-agent-scenes/
├── .github/workflows/crawl.yml   # 定时抓取（待添加）
├── scripts/                      # 抓取与结构化脚本（待添加）
│   ├── crawl.py                  #   抓 HN / GitHub
│   ├── enrich.py                 #   LLM 结构化打标签评分
│   └── dedupe.py                 #   去重
├── data/scenes.json              # 数据库
├── index.html                    # 前端入口
├── app.js                        # 筛选 / 排序 / 搜索
├── style.css                     # 样式
└── README.md
```

## 本地运行

```bash
# 任意静态服务器即可（因为前端用 fetch 读 JSON）
python3 -m http.server 8777
# 打开 http://localhost:8777
```

## 抓取脚本（数据引擎）

`scripts/crawl.py` 读取 `data/sources.json`，自动抓取 → 判别 → 去重 → 评分 → 写入 `data/scenes.json`。

```bash
# 干跑：不调 LLM，用规则桩验证全链路（不花钱，会真的抓 RSS）
python3 scripts/crawl.py --mock --limit 10

# 正式跑：需先设置 DeepSeek key
export DEEPSEEK_API_KEY=sk-xxxx
python3 scripts/crawl.py

# 调参：每源最多处理条数
python3 scripts/crawl.py --limit 20
```

处理流水线（详见各步注释）：
1. **fetch** 逐源抓原始条目
2. **pre_filter** 关键词命中 + 链接去重（先于 LLM，省钱）
3. **extract** DeepSeek 判别"可复用场景 vs 易逝资讯"，只抽前者
4. **dedupe** 同一玩法多源出现则合并，提及次数 +1
5. **score** 热度 = 提及次数 × 源权重 + 新颖度，低于 `HEAT_THRESHOLD` 不入库
6. **write** 增量写入 scenes.json

## 自动化（GitHub Actions）

`.github/workflows/crawl.yml` 每天定时跑并自动 commit。启用步骤：
1. 仓库 Settings → Secrets and variables → Actions → 新增 `DEEPSEEK_API_KEY`
2. Actions 页面可手动触发（支持勾选 mock 模式先验证）
3. 跑完自动提交 `data/scenes.json`，触发 Pages 重新部署

## 部署到 GitHub Pages

1. 把本目录推到 GitHub 仓库
2. Settings → Pages → Source 选 `main` 分支根目录
3. 访问 `https://<用户名>.github.io/<仓库名>/`

## 路线图

- [x] 前端展示（筛选 / 排序 / 搜索 / 主题）
- [x] 示例数据
- [x] HN + YouTube + newsletter 自动抓取脚本
- [x] GitHub Actions 定时调度
- [x] LLM 自动结构化与评分（判别"场景 vs 资讯"）
- [ ] 接入真实 DeepSeek key 跑首轮正式数据
- [ ] 人工投喂中文源（小红书 / 公众号链接 → 自动入库）
- [ ] 每周精选自动汇总

## 数据获取说明（重要）

各数据源抓取难度差异极大：

- 🟢 **易**：Hacker News（免费 API）、GitHub（官方 API）
- 🟡 **中**：Reddit（限流，需 key）、ProductHunt（需 token）
- 🔴 **难**：小红书（强反爬）、微信公众号（无开放 API）、X（API 极贵）

因此采用**「海外源自动抓取 + 中文源人工投喂」**的混合策略：机器负责能自动化的部分，人负责发现优质中文内容、AI 负责加工入库。

---

*更新机制：自动追踪 + 人工精选*
