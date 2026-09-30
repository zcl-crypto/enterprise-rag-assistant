# 企业 RAG 知识库助手：详细实施方案

> 状态：项目路线图，不代表所有功能均已实现。当前已完成解析、索引、基础鉴权与 API 的测试基线；实际完成项和验证证据见 [实施记录](progress.md)。
> 场景：虚构企业“星桥科技”的内部制度知识库，所有演示语料明确标注为虚构。

## 1. 目标与范围

管理员上传、替换、删除制度文档；员工根据自身权限检索和提问。系统回答必须有可打开的文档来源，证据不足时说明无法确认。项目用于 AI 应用开发 / Agent 开发岗位作品集，重点展示完整数据生命周期、检索质量、权限与评测。

| 项目 | 确定要求 |
| --- | --- |
| 输入 | PDF、DOCX、Markdown、TXT、HTML |
| 流程 | 统一解析 → Document → Chunk → 本地 Embedding → 检索/重排 → 国内生成 API |
| 语料 | 扩充虚构企业制度，支持上传、替换、删除，并保留版本元数据 |
| 成本 | 国内免费 API 优先；本地 Embedding/Reranker；演示费用目标 0～30 元 |
| 交付 | 本地 Docker Compose、GitHub README、架构图、评测报告、演示视频 |
| 暂缓 | 公网部署、多租户平台、复杂 Agent 编排 |

首版支持有文本层的 PDF。扫描 PDF 可作为第二阶段的可选 OCR 能力；未启用 OCR 时应显示“需要 OCR”，不能把空解析当作成功。复杂表格和页码定位须通过专门样例验证，不能保证所有文件都准确。

## 2. 目标架构

```text
React/Vite Web
    ↓
FastAPI (鉴权、文档管理、检索、问答、引用查看)
    ├── PostgreSQL (用户、文档、版本、任务、chunk 清单、审计)
    ├── Qdrant (向量、检索 payload)
    ├── Worker (解析、切分、Embedding、索引、清理)
    └── 国内 LLM API (仅答案生成)
```

Compose 已配置并实测 `web`、`api`、`worker`、`postgres`、`qdrant`，另设一次性的模型下载和数据库初始化任务。worker 使用数据库任务表领取任务；首版不增加 Redis。原文件、数据库、Qdrant 数据与模型缓存均挂载持久卷，容器删除并重建后的数据保持性已经验证。无 API Key 时可运行上传、检索和引用演示模式；完整生成问答需要配置 Key。无 Docker 时可使用 API 进程内的 Qdrant 本地模式验证主要交互，该模式不是 Compose 部署架构。

### 选型

| 模块 | 默认选择 | 说明 |
| --- | --- | --- |
| 后端 | Python 3.11/3.12、FastAPI | 容器中固定 Python 版本；本机 3.13 不作为容器依赖基准。 |
| 解析 | PDFium 提取文本层；DOCX/HTML 使用 Docling；Markdown/TXT 使用轻量解析器 | 将五种格式映射到项目统一结构；PDF 基础版保留页码，复杂版面和表格识别仍需增强。 |
| Embedding | `BAAI/bge-small-zh-v1.5` | 中文优先，512 维；先做轻量本地基线。 |
| Reranker | `BAAI/bge-reranker-base` | 仅重排前 10～20 个候选；低内存机器可关闭。 |
| 检索 | Qdrant dense 基线；评测后加入 BM25 sparse + RRF | 中文 BM25 的 tokenizer 在入库与查询时必须一致。 |
| 生成 | 智谱 OpenAI 兼容接口，本机使用 `glm-4-flash-250414` | 模型 ID 可配置；免费政策、可用型号和限流以调用当天平台为准。 |
| 前端 | React + Vite | 问答、引用原文、文档列表、上传进度、版本与删除操作。 |

当前实现选择 PDFium 的文本层提取作为 PDF 默认路径，因为本机 Docling 完整 PDF 版面管线首次准备模型时未能完成验证。Docling 仍用于 DOCX/HTML；后续可增设完整 PDF 版面解析模式并单独评测。Qdrant 支持混合检索和过滤。GLM 的调用封装只依赖模型 ID、Base URL 和 Key，以便免费政策变化时切换服务商。

## 3. 数据模型

| 实体 | 关键字段 | 用途 |
| --- | --- | --- |
| `users` | id、账号、密码哈希、角色、部门、状态 | 演示账号与后端权限校验。 |
| `documents` | id、标题、部门、可见角色、`active_version_id`、删除时间 | 逻辑文档及当前对外版本。 |
| `document_versions` | id、document_id、版本号、文件格式、SHA-256、存储路径、上传时间、生效日期、状态 | 每次内容更换生成新版本。 |
| `chunks` | id、version_id、章节路径、页码/字符范围、顺序、正文、embedding_model | 引用和索引清单。 |
| `ingestion_jobs` | id、version_id、状态、尝试次数、错误、起止时间 | 异步索引与失败重试。 |
| `audit_events` | id、操作者、动作、对象、结果、时间 | 追踪上传、发布、删除和权限变更。 |

版本状态：`UPLOADED → PROCESSING → READY → ACTIVE`；失败为 `FAILED`，旧版本为 `RETIRED`，扫描文件待处理为 `NEEDS_OCR`。PostgreSQL 是版本与权限的权威数据源，Qdrant 的 payload 用于检索过滤和引用定位。原文件使用随机 ID 命名，原文件名只用于展示。

## 4. 文档到索引

1. API 校验管理员身份、扩展名和实际格式、文件大小（默认上限 20 MB），写临时文件并创建任务。
2. worker 解析文档，映射成统一 `ParsedDocument`：文档元信息、标题层级、段落、页码与原文位置。PDF 基础版按页提取文本；表格结构识别作为增强项。
3. 空文本、乱码和解析错误进入失败状态，界面显示原因。扫描 PDF 在未启用 OCR 时进入 `NEEDS_OCR`。
4. 按章节与段落切分，初始目标约 300～450 个中文字符，少量重叠；表格保留表头与行关系。最终按 Embedding tokenizer 的 512-token 上限再次检查。
5. 批量生成 Embedding，写入 chunk 清单并 upsert 到 Qdrant。点 ID 由版本与 chunk 顺序稳定生成，重试不能制造重复片段。
6. 比对解析 chunk 数和写入数，校验通过后标记 `READY`。管理员发布后才成为 `ACTIVE`。

引用定位优先使用 PDF 页码；无页码的格式显示章节路径与段落位置。无法可靠定位时只展示文档与章节，不虚构页码。

## 5. 删除与更换语料

**更换**：对同一 `document_id` 上传新文件，生成新 `version_id`。旧版继续服务；新版本全部解析和索引成功后进入 `READY`。管理员发布时在 PostgreSQL 单事务切换 `active_version_id`，旧版成为 `RETIRED`，后台再删除旧向量。新版本失败时旧版不受影响。

**删除**：管理员删除文档时，先在 PostgreSQL 标记删除并取消活跃版本，再后台清除 Qdrant 点和原文件。清理失败可重试，审计记录保留。查询和打开引用时都重新核对 PostgreSQL 状态。

检索前从 PostgreSQL 获取当前用户可访问的活跃版本 ID，作为 Qdrant 过滤条件；生成答案前再次校验候选引用。这样旧向量在异步清理期间仍存在，也不会进入回答。该版本 ID 过滤适合本项目数十份文档的规模；扩大规模时需重新设计索引发布方式。

必须通过三个端到端测试：新版本发布后旧答案不可见；替换失败时旧版仍可用；删除后搜索、问答和旧引用链接都不能访问该文档。

## 6. 查询链路

1. 后端根据登录账号确定部门和角色；客户端不能传入任意角色覆盖权限。
2. Qdrant 只检索当前有权限的活跃版本，先取约 20 个候选。加入 hybrid 时对 dense 与 BM25 结果做 RRF 融合。
3. 本地 Reranker 重排前 10～20 个候选，选前 4～6 个片段。
4. 给 LLM 的上下文为带引用 ID 的片段；生成文本与引用 ID。服务端验证引用 ID 属于当前授权候选与活跃版本。
5. 证据不足则拒答。API 超时、限流或无 Key 时显示明确状态，保留检索结果和来源供查看。

生成服务不持有数据库和文件操作工具。检索到的文档内容按不可信数据处理；权限在代码中执行。输出 Markdown 渲染需清理危险 HTML。每次请求记录各阶段耗时、模型名、token 用量和请求 ID，不记录 API Key。

## 7. 接口与页面

| 接口 | 功能 |
| --- | --- |
| `POST /api/v1/auth/login` | 登录演示账号。 |
| `GET /api/v1/auth/me` | 获取当前账号、角色与部门。 |
| `GET /api/v1/documents` | 根据身份列出可见文档与活跃版本 ID。 |
| `GET /api/v1/documents/{id}/versions` | 管理员查看版本与索引任务状态。 |
| `POST /api/v1/documents` | 上传新文档。 |
| `POST /api/v1/documents/{id}/versions` | 上传替换版本。 |
| `POST /api/v1/documents/{id}/versions/{version_id}/activate` | 发布已就绪版本。 |
| `DELETE /api/v1/documents/{id}` | 删除文档并启动索引清理。 |
| `GET /api/v1/documents/{id}/source` | 权限校验后打开活跃原文/引用位置。 |
| `POST /api/v1/search` | 返回检索片段及来源，可用于调试和无 Key 演示。 |
| `POST /api/v1/chat` | 返回答案、引用、耗时、模型名及请求 ID。 |
| `GET /api/v1/jobs/{id}` | 查看处理进度与失败原因。 |
| `POST /api/v1/jobs/{id}/retry` | 管理员手动重试可恢复的失败任务。 |
| `GET /api/v1/audit` | 管理员查看最近的操作审计记录。 |
| `GET /api/v1/usage` | 管理员查看 UTC 当日 Token 额度和最近问答请求记录。 |

前端包含问答、知识库管理和管理员评测三个视图。演示账号至少有管理员、全员可见资料的普通员工、受限部门员工。页面展示角色便于演示，但权限必须由后端执行。

## 8. 虚构语料与评测

扩充至 25～40 份虚构制度，覆盖人事、财务、采购、IT、安全等领域。专门加入旧版/新版冲突、相近标题、表格、跨文档问题、无答案问题和越权问题。五种格式均有独立内容；同一内容的格式转换副本只用于解析回归，不能同时索引，避免重复片段污染结果。

人工标注约 80 道问题，字段包括问题、用户角色、答案要点、支持文档/章节、预期拒答与否。冻结测试集后做三组对照：dense、dense+BM25、dense+BM25+rerank。

报告 `Recall@5`、`MRR`、答案要点正确率、引用支持率、无答案拒答率、越权检索数、`p50/p95` 延迟、token 用量与估算费用。自动评分至少抽查 20 条。README 只写真实测量值，并同时披露语料规模和评测方法。

## 9. 分阶段交付与验收

| 阶段 | 交付 | 验收条件 |
| --- | --- | --- |
| A. 环境与数据 | Compose、迁移、虚构语料、五格式夹具 | `docker compose up --build` 启动；无 Key 时可进入检索模式。 |
| B. 解析与索引 | 上传、任务、解析、切分、Embedding、Qdrant | 五格式回归通过；失败可见；重复任务不产生重复 chunk。 |
| C. 检索与问答 | 权限、引用、生成适配器、本地重排 | 引用可打开；无证据拒答；越权检索与原文访问被阻止。 |
| D. 生命周期 | 新版本发布、删除、清理重试、审计 | 替换成功/失败/删除三类端到端测试通过。 |
| E. 评测与展示 | 80 题评测、对照报告、README、架构图、视频 | 评测可复现；视频演示上传、问答、权限、替换、删除与失败处理。 |

按每周约 10～15 小时估算，A～E 约 5～7 周。以验收条件决定阶段完成，不以日历日期替代验证。

## 10. 约束与待验证项

- 当前工作机已完成 Docker Compose 一键启动、Alembic `0003`、PostgreSQL/Qdrant 服务端、持久卷、双 Worker 批处理和真实模型录屏验证；长时间压力测试、异常进程恢复和公网环境仍不在首版验收范围内。
- 模型权重与 Docling 组件首次使用需要下载。Compose 持久化缓存；README 提供预下载和离线挂载方式。建议约 16 GB 内存与充足磁盘；仅 8 GB 时关闭 OCR、限制 worker 并发，并实测是否启用 Reranker。
- 完整回答需要用户自己的国内 API Key。Key 放 `.env`，不得提交 GitHub。“一键启动”指完成一次 Key 配置与模型下载后用 Compose 启动；无 Key 时提供检索演示。
- 智谱免费额度和限流可能变化。配置每日 token 上限与模型切换，不把零费用当作永久保证。
- PDF 扫描件 OCR、复杂表格、页码定位是质量风险；在版本说明与演示中标明当前覆盖范围。

## 参考资料

- Docling 支持格式：https://docling-project.github.io/docling/usage/supported_formats/
- Qdrant 混合检索：https://qdrant.tech/documentation/search/text-search/hybrid-search/
- Qdrant BM25 语言配置：https://qdrant.tech/documentation/search/text-search/full-text-search/
- 智谱免费模型：https://docs.bigmodel.cn/cn/guide/models/free/glm-4.7-flash
- 智谱 OpenAI 兼容接口：https://docs.bigmodel.cn/cn/guide/develop/openai/introduction
- BGE Embedding：https://huggingface.co/BAAI/bge-small-zh-v1.5
- BGE Reranker：https://huggingface.co/BAAI/bge-reranker-base
