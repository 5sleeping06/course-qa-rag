# B1 · 课程知识库智能问答（RAG）

仓库地址：<https://github.com/5sleeping06/course-qa-rag>

> 面向《Java 语言及网络编程》课程报告 · 单人 · AI 工程化路线

面向：《Java 语言及网络编程》课程报告 · 单人 · 7 天 · AI 工程化路线

## 包里有什么

| 文件 | 作用 | 谁看 |
| --- | --- | --- |
| `B1-RAG问答-需求分析与周计划.docx` | 需求分析 + 可验收规格 + 技术选型 + 一周计划 + 报告章节映射 | 你、老师 |
| `spec/skill.course-qa.md` | SDD 规约：给 AI agent 读的能力包（接口、验收标准、禁止事项） | AI agent、你 |
| `eval/evalset.jsonl` | 30 题评测集（含应拒答、提示注入、越权三类负样本） | 评测脚本、你 |
| `eval/run_eval.py` | 评测执行器（零依赖，直接打你本机 8080） | 你 |
| `README.md` | 本文件 | 你 |

## 使用顺序

1. **Day 0（今晚 2 小时）**：装 Maven、确认模型 API Key、把课程资料丢进 `materials/`。
2. **Day 1**：把 `spec/skill.course-qa.md` 丢给 AI agent 生成骨架代码；同时人工核对 `eval/evalset.jsonl` 里标了 `"verify":"pending"` 的题。
3. **Day 2–4**：按 docx 里的每日任务推进，每天收工前用 `python eval/run_eval.py --dry-run` 确认评测集没被改坏。
4. **Day 5 起**：`python eval/run_eval.py` 打分，把结果贴进报告「系统验证」章节。

## 三条不能破的规矩

1. **评测集 Day 1 冻结**。冻结之后只允许「追加新题」并明确记录，不允许为了让分数好看去改题目或参考答案——这是说明里「可验收规格」的底线，答辩时老师一问就穿。
2. **先跑通最窄链路再扩功能**。上传一份文档 → 问一句 → 出带引用的流式回答。这条链路没通之前，不要碰多轮对话、不要碰前端美化。
3. **AI 生成的代码必须跑评测**。改完就跑 `run_eval.py`，用数字说话，不要凭手感判断「应该没问题」。

## 环境现状（已在你机器上确认）

| 项 | 状态 | 处理 |
| --- | --- | --- |
| JDK | 25.0.4.1（Temurin）✅ | 可直接用；若遇 Spring Boot 反射/字节码报错，装 JDK 21 LTS 回退 |
| Maven | ✅ 3.9.9，装在 `D:\tools\maven` | 已配阿里云镜像（`~/.m2/settings.xml`）；新开终端后 `mvn -v` 生效 |
| Docker | ❌ 未安装（已放弃，非必需） | 本机装它要下 1.3GB 且 GitHub 通道被切断；脚本留在 `install-docker*.cmd`，哪天想装直接双击 |
| Git | ✅ 已安装 | 直接 init 仓库 |
| Python | ✅ 有 | 跑评测脚本用（`python eval/run_eval.py`） |

## 如何运行（当前已可跑通）

**最省事的方式：双击 `start.cmd`。** 它用绝对路径调用 java、自己切到项目目录，不依赖 PATH，也不依赖你从哪个目录打开终端。

需要重新编译时双击 `build.cmd`（同样用绝对路径调 Maven）。

命令行方式（注意：`mvn` 需要是 PATH 生效之后新开的窗口，否则会提示「无法将 mvn 项识别为…」）：

```powershell
cd D:\study\projecct\b
& 'D:\tools\maven\bin\mvn.cmd' clean package -DskipTests     # 免 PATH 的写法
& 'C:\Users\28443\jdk\jdk-25.0.4.1+1\bin\java.exe' -jar 'target\course-qa-0.1.0.jar'
```

如果旧窗口里 `mvn` 找不到，不必重开窗口，执行下面一行刷新 PATH：

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
```

浏览器打开 <http://127.0.0.1:8080>，上传课程资料后提问即可看到逐字回答 + 引用。

> 启动后要等控制台出现 `Started QaApplication` 再打开网址，通常 3–6 秒（要加载索引）。窗口关掉服务就停了。

**用 DeepSeek 跑（推荐）**：双击 `start-ai.cmd`，它从 `.env` 读密钥并启动。

**离线模式**（不花钱、断网可用）：双击 `start.cmd`。

> ⚠️ `start.cmd` 是 mock 模式：它**不调用大模型**，只是把检索到的原文片段抄一段，
> 不具备归纳与比较能力，不能用来评价回答质量。看效果请用 `start-ai.cmd`。

批量入库与实测：

```powershell
python ingest_materials.py --ask     # 上传 materials/ 下全部文件，然后跑 6 个领域问题
python verify_qa.py                  # 验拒答行为 + 流式事件顺序
```

命令行单次问答（PowerShell 里 **不要用 `curl`**，它是 `Invoke-WebRequest` 的别名；用 `curl.exe`）：

```powershell
curl.exe -s -X POST http://127.0.0.1:8080/api/chat -H "Content-Type: application/json" -d '{\"question\":\"能源大数据的关键技术包括哪些？\"}'
```

## 当前进度

| 项 | 状态 |
| --- | --- |
| 骨架（22 个源文件，可编译可启动） | ✅ |
| 上传 → 解析（txt/md/pdf/docx）→ 分块 → 索引落盘 → 重启恢复 | ✅ |
| 检索：BM25 词法检索（中文二元组，按需重建索引） | ✅ |
| 真实大模型：DeepSeek `deepseek-chat`，OpenAI 兼容协议 | ✅ 实测通过 |
| 同步问答 `/api/chat` + 流式 `/api/chat/stream`（SSE） | ✅ 首字 184ms |
| 引用溯源（docName + 块序号 + 片段 + 分数） | ✅ |
| 拒答：检索阈值 + 模型落地性判定（只看回答开头）→ `status=refused` 且清空引用 | ✅ 8/8 负样本通过 |
| 离线 mock 模型（断网演示兜底） | ✅ |
| 向量检索（`retrieval-mode=vector`） | ✅ 代码保留，缺 embedding 服务 |
| 评测集（30 题，能源大数据课件域，从原文块反向生成） | ✅ 见 `eval/BASELINE.md` |
| 基线成绩 | ✅ 答对 22/22、拒答 8/8、P50 1.19s、P95 1.62s |
| 参数扫描（分块 300/400/600/800 × topK 3/5/8） | ✅ 见 `eval/SWEEP.md` 与 `eval/charts/sweep.png` |
| 加难集（10 同义改写 + 12 跨块多跳） | ✅ 答对率 95.5% → 63.6%，见 `eval/HARD.md` |
| 令牌桶限流（按 IP，30 次/分，429 + Retry-After） | ✅ 突发 40 次 → 32 通过 / 8 拒绝 |
| 并发压测（服务端 / 端到端 / 限流三组） | ✅ 见 `eval/PERFORMANCE.md` |
| 多轮会话（会话存储 + 指代改写 + 历史入提示词） | ✅ 2/3 用例带历史更优，见 `tools/verify_multiturn.py` |

## 性能结论（一句话版）

服务端 **1152 QPS**（P50 10ms），端到端只有 **4.8 QPS**（P50 1.6s）——差三个数量级，瓶颈全在上游模型。
并发 1→5 吞吐涨 4.9 倍，5→10 只涨 58%，再加并发只会拉长 P95。
端到端 1.6 秒 vs 流式首字 184ms，**感知延迟差 8 倍**，这是选 SSE 最硬的理由。
限流按 IP 计数在教室 NAT 下会误伤全教室，已作为设计隐患写进报告。

```powershell
python tools/run_load_suite.py    # 三组压测，自动起停服务（约 2 分钟）
```

## 加难集结论（一句话版）

换一套题，同一系统答对率从 **95.5% 掉到 63.6%**。分题型看：同义改写 **100%**（中文二元组比预想稳），
跨块多跳只有 **33%**。再拆一层：两跳都检索到时答对 4/8，缺一跳时 0/4——
**缺跳必然错，但检索到了也只有一半能合起来**，瓶颈在证据整合而非检索。
详见 [eval/HARD.md](<eval/HARD.md>)。

```powershell
python eval/build_evalset_hard.py   # 生成加难集（需 API Key）
python eval/run_eval.py --evalset eval/evalset-hard.jsonl --out eval/result-hard.csv
```

## 参数扫描结论（一句话版）

分块 **400**、topK **5** 是交付配置。分块加大索引更省但生成更慢（800 时 P95 反升到 1763ms）；
topK 从 5 加到 8 反而更差（答对率 95.5% → 90.9%，P50 涨 38%）——上下文稀释。
两者都已写成报告素材，见 [eval/SWEEP.md](<eval/SWEEP.md>)。

```powershell
python eval/sweep.py          # 重跑扫描（约 5 分钟，会自动起停服务）
python eval/make_charts.py    # 重新出图
```

## 一次 badcase 的排查记录

用户反馈「能源大数据的关键技术包括哪些」答偏，排查出三个叠加问题（启动方式用错 mock、
PPT 页眉噪声、答案横跨多块），修复四项并做了回归。
详见 [eval/BADCASE-2026-11-27.md](<eval/BADCASE-2026-11-27.md>)。

## 评测怎么跑

```powershell
# 1. 重建评测集（需要 API Key，会调用模型出题）
python eval/build_evalset.py

# 2. 启动服务后跑评测
python eval/run_eval.py --evalset eval/evalset.jsonl --out eval/result-v1.csv

# 宽松口径（关键术语命中 60% 即算对），用于对比
python eval/run_eval.py --min-hit-ratio 0.6 --out eval/result-v1-loose.csv
```

评测过程中发现并修掉了 4 个真实缺陷（短答案误判拒答、先答后补充误判、拒绝编造未识别、脚本缺就绪等待），
过程和局限都写在 [eval/BASELINE.md](<eval/BASELINE.md>) 里——报告「系统验证」一章可以直接用。

## 为什么不用向量检索

DeepSeek **没有** `/embeddings` 接口（实测 404）。为了向量化再引入第二个供应商与密钥不划算，
所以主检索器用 BM25：中文按字符二元组切词，完全离线、可解释、结果可复现。
`retrieval-mode=vector` 的分支保留着，将来随便接一个 OpenAI 兼容的 embedding 服务即可切换。

更完整的取舍与实测数据见 `B1-RAG问答-需求分析与周计划.docx` 第九章「实施变更记录」。


