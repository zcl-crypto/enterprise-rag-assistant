import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import {
  AlertCircle, ArrowUpRight, BarChart3, BookOpen, Check, ClipboardList, Database,
  FileText, LogOut, RefreshCw, RotateCcw, Search, Send, Shield,
  Trash2, Upload, X,
} from "lucide-react";
import {
  ApiError, client, type AuditEvent, type ChatResult, type DocumentVersion, type EvaluationDashboard,
  type KnowledgeDocument, type SearchHit, type UsageSummary, type UserProfile,
} from "./api";

type View = "chat" | "documents" | "evaluation" | "audit";
type Mode = "chat" | "search";
type Exchange = {
  id: number;
  question: string;
  mode: Mode;
  status: ChatResult["status"] | "search" | "error";
  answer: string | null;
  sources: SearchHit[];
  error?: string;
  model?: string;
};

const TOKEN_KEY = "xingqiao-rag-token";

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "登录已过期，请重新登录。";
    if (error.status === 403) return "当前账号没有此操作权限。";
    return error.message;
  }
  return error instanceof Error ? error.message : "请求失败，请稍后重试。";
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(status: string): string {
  return ({
    UPLOADED: "待处理", PROCESSING: "处理中", READY: "待发布", ACTIVE: "已发布",
    RETIRED: "已停用", FAILED: "失败", NEEDS_OCR: "需要 OCR",
    PENDING: "待处理", RUNNING: "处理中", DONE: "已完成", CANCELLED: "已取消",
  } as Record<string, string>)[status] ?? status;
}

function Login({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await client.login(username, password);
      onLogin(result.access_token);
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-mark"><BookOpen size={25} aria-hidden="true" /><span>星桥科技</span></div>
      <form className="login-panel" onSubmit={submit}>
        <div className="eyebrow">内部知识库</div>
        <h1>登录工作台</h1>
        <label htmlFor="username">账号</label>
        <select id="username" value={username} onChange={(event) => setUsername(event.target.value)}>
          <option value="admin">管理员</option>
          <option value="employee">普通员工</option>
          <option value="procurement">采购部员工</option>
        </select>
        <label htmlFor="password">密码</label>
        <input id="password" type="password" autoComplete="current-password" value={password}
          onChange={(event) => setPassword(event.target.value)} required />
        {error && <p className="form-error" role="alert"><AlertCircle size={16} />{error}</p>}
        <button className="button primary login-submit" type="submit" disabled={busy}>
          {busy ? <RefreshCw className="spin" size={17} /> : <ArrowUpRight size={17} />}
          {busy ? "登录中" : "登录"}
        </button>
      </form>
      <div className="login-footnote">虚构企业演示环境</div>
    </main>
  );
}

function SourceList({
  sources, documents, onOpen,
}: {
  sources: SearchHit[];
  documents: KnowledgeDocument[];
  onOpen: (source: SearchHit) => void;
}) {
  if (!sources.length) return <p className="muted empty-line">暂无可引用片段</p>;
  const titles = new Map(documents.map((document) => [document.id, document.title]));
  return (
    <div className="source-list">
      {sources.map((source, index) => (
        <article className="source-item" key={`${source.chunk_id}-${index}`}>
          <div className="source-topline">
            <span className="source-number">{String(index + 1).padStart(2, "0")}</span>
            <span className="source-title">{titles.get(source.document_id) ?? "授权文档"}</span>
            <button className="icon-button" type="button" title="打开原文" aria-label="打开原文"
              onClick={() => onOpen(source)}><ArrowUpRight size={16} /></button>
          </div>
          <div className="source-meta">
            {source.headings.length > 0 && <span>{source.headings.join(" / ")}</span>}
            {source.page_number != null && <span>第 {source.page_number} 页</span>}
          </div>
          <p className="source-excerpt">{source.text}</p>
        </article>
      ))}
    </div>
  );
}

function ChatWorkbench({
  token, documents, onOpenSource,
}: {
  token: string;
  documents: KnowledgeDocument[];
  onOpenSource: (source: SearchHit) => void;
}) {
  const [mode, setMode] = useState<Mode>("chat");
  const [question, setQuestion] = useState("");
  const [exchanges, setExchanges] = useState<Exchange[]>([]);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const nextId = useRef(1);
  const active = exchanges.find((exchange) => exchange.id === activeId);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const query = question.trim();
    if (!query || busy) return;
    setQuestion("");
    setBusy(true);
    const id = nextId.current++;
    try {
      if (mode === "search") {
        const sources = await client.search(token, query);
        setExchanges((current) => [...current, { id, question: query, mode, status: "search", answer: null, sources }]);
      } else {
        const result = await client.chat(token, query);
        setExchanges((current) => [...current, {
          id, question: query, mode, status: result.status, answer: result.answer,
          sources: result.citations, model: result.model,
        }]);
      }
    } catch (cause) {
      setExchanges((current) => [...current, {
        id, question: query, mode, status: "error", answer: null, sources: [], error: errorText(cause),
      }]);
    } finally {
      setActiveId(id);
      setBusy(false);
    }
  }

  function answerText(exchange: Exchange): string {
    if (exchange.answer) return exchange.answer;
    if (exchange.status === "search") return exchange.sources.length ? `找到 ${exchange.sources.length} 条相关片段。` : "没有找到相关片段。";
    if (exchange.status === "search_only") return "已找到相关依据；当前未配置生成模型，请查看右侧原文。";
    if (exchange.status === "insufficient_evidence") return "知识库中没有足够依据确认此问题。";
    if (exchange.status === "invalid_citation") return "生成内容的引用无法验证，本次回答未展示。";
    if (exchange.status === "model_unavailable") return "生成模型暂时不可用，已保留检索到的依据。";
    if (exchange.status === "quota_exceeded") return "今天的生成额度已用尽，仍可查看检索到的依据。";
    return exchange.error ?? "请求失败。";
  }

  return (
    <div className="workspace chat-workspace">
      <section className="chat-main" aria-label="问答区">
        <div className="section-heading">
          <div><div className="eyebrow">知识检索</div><h1>问答工作台</h1></div>
          <div className="mode-switch" role="group" aria-label="查询模式">
            <button type="button" className={mode === "chat" ? "selected" : ""} onClick={() => setMode("chat")}>问答</button>
            <button type="button" className={mode === "search" ? "selected" : ""} onClick={() => setMode("search")}>检索</button>
          </div>
        </div>
        <div className="conversation" aria-live="polite">
          {!exchanges.length && (
            <div className="conversation-empty">
              <div className="empty-symbol"><Search size={27} strokeWidth={1.7} /></div>
              <h2>查询内部制度</h2>
              <p>输入具体问题，结果会附上可查看的来源。</p>
            </div>
          )}
          {exchanges.map((exchange) => (
            <div className="exchange" key={exchange.id}>
              <div className="question-line"><span className="speaker-label">你</span><p>{exchange.question}</p></div>
              <div className={`answer-line ${activeId === exchange.id ? "active" : ""}`}>
                <div className="answer-label"><span className="speaker-label system">知识库</span>
                  <span className="mode-label">{exchange.mode === "search" ? "检索" : "问答"}</span></div>
                <p>{answerText(exchange)}</p>
                <div className="answer-footer">
                  <button type="button" className="text-button" onClick={() => setActiveId(exchange.id)}>
                    <FileText size={15} /> 来源 {exchange.sources.length}
                  </button>
                  {exchange.model && <span className="muted">{exchange.model}</span>}
                </div>
              </div>
            </div>
          ))}
          {busy && <div className="loading-answer"><RefreshCw className="spin" size={17} /> 正在检索知识库</div>}
        </div>
        <form className="query-form" onSubmit={submit}>
          <label className="sr-only" htmlFor="question">输入问题</label>
          <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)}
            placeholder="例如：采购金额超过一万元，需要怎样比价？" maxLength={2000} rows={3}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }} />
          <button className="button primary send-button" type="submit" disabled={busy || !question.trim()} title="发送问题">
            <Send size={17} /> 发送
          </button>
        </form>
      </section>
      <aside className="evidence-pane" aria-label="引用来源">
        <div className="pane-heading"><div><div className="eyebrow">可核对的依据</div><h2>来源片段</h2></div>
          <span className="count-badge">{active?.sources.length ?? 0}</span></div>
        <SourceList sources={active?.sources ?? []} documents={documents} onOpen={onOpenSource} />
      </aside>
    </div>
  );
}

type UploadKind = "new" | "replace";

function UploadDialog({ kind, document, token, onClose, onSaved }: {
  kind: UploadKind;
  document: KnowledgeDocument | null;
  token: string;
  onClose: () => void;
  onSaved: (documentId: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [visibility, setVisibility] = useState("all");
  const [department, setDepartment] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    if (effectiveDate) form.append("effective_date", effectiveDate);
    if (kind === "new") {
      form.append("title", title.trim());
      form.append("allowed_roles", visibility === "admin" ? "admin" : "employee");
      if (visibility === "department") form.append("department", department.trim());
    }
    setBusy(true);
    setError("");
    try {
      const receipt = await client.upload(token, form, kind === "replace" ? document?.id : undefined);
      onSaved(receipt.document_id);
    } catch (cause) {
      setError(errorText(cause));
      setBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="dialog" role="dialog" aria-modal="true" aria-labelledby="upload-title">
        <div className="dialog-heading"><div><div className="eyebrow">知识库管理</div>
          <h2 id="upload-title">{kind === "replace" ? `替换 ${document?.title}` : "上传文档"}</h2></div>
          <button className="icon-button" type="button" title="关闭" aria-label="关闭" onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={submit} className="dialog-form">
          {kind === "new" && <>
            <label htmlFor="document-title">文档标题</label>
            <input id="document-title" value={title} onChange={(event) => setTitle(event.target.value)} maxLength={255} required />
            <label htmlFor="visibility">可见范围</label>
            <select id="visibility" value={visibility} onChange={(event) => setVisibility(event.target.value)}>
              <option value="all">所有员工</option>
              <option value="department">指定部门</option>
              <option value="admin">仅管理员</option>
            </select>
            {visibility === "department" && <>
              <label htmlFor="department">部门名称</label>
              <input id="department" value={department} onChange={(event) => setDepartment(event.target.value)}
                placeholder="例如：采购部" required />
            </>}
          </>}
          <label htmlFor="effective-date">制度生效日期（可选）</label>
          <input id="effective-date" type="date" value={effectiveDate}
            onChange={(event) => setEffectiveDate(event.target.value)} />
          <label htmlFor="document-file">文件</label>
          <input id="document-file" type="file" accept=".pdf,.docx,.md,.txt,.html,.htm" required
            onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          <p className="field-note">PDF、DOCX、Markdown、TXT、HTML；最大 20 MB</p>
          {error && <p className="form-error" role="alert"><AlertCircle size={16} />{error}</p>}
          <div className="dialog-actions"><button className="button subtle" type="button" onClick={onClose}>取消</button>
            <button className="button primary" type="submit" disabled={busy || !file || (kind === "new" && !title.trim())}>
              {busy ? <RefreshCw className="spin" size={16} /> : <Upload size={16} />}
              {busy ? "提交中" : "提交处理"}
            </button></div>
        </form>
      </section>
    </div>
  );
}

function DocumentWorkspace({ token, user, documents, refreshDocuments, onNotice, onOpenDocument }: {
  token: string;
  user: UserProfile;
  documents: KnowledgeDocument[];
  refreshDocuments: () => Promise<void>;
  onNotice: (message: string) => void;
  onOpenDocument: (documentId: string) => void;
}) {
  const isAdmin = user.role === "admin";
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [versions, setVersions] = useState<DocumentVersion[]>([]);
  const [upload, setUpload] = useState<UploadKind | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const pendingSelection = useRef<string | null>(null);
  const detailPane = useRef<HTMLElement | null>(null);
  const selected = documents.find((document) => document.id === selectedId) ?? null;
  const filteredDocuments = documents.filter((document) =>
    `${document.title} ${document.department ?? ""}`.toLocaleLowerCase().includes(filter.trim().toLocaleLowerCase())
  );

  function selectDocument(id: string) {
    setSelectedId(id);
    if (window.matchMedia("(max-width: 700px)").matches) {
      window.setTimeout(() => detailPane.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    }
  }

  useEffect(() => {
    if (pendingSelection.current) {
      if (documents.some((document) => document.id === pendingSelection.current)) {
        setSelectedId(pendingSelection.current);
        pendingSelection.current = null;
      }
      return;
    }
    if (documents.length && !documents.some((document) => document.id === selectedId)) {
      setSelectedId(documents[0].id);
    }
    if (!documents.length) setSelectedId(null);
  }, [documents, selectedId]);

  const refreshVersions = useCallback(async () => {
    if (!isAdmin || !selectedId) {
      setVersions([]);
      return;
    }
    try {
      setVersions(await client.versions(token, selectedId));
    } catch (cause) {
      setError(errorText(cause));
    }
  }, [isAdmin, selectedId, token]);

  useEffect(() => {
    void refreshVersions();
    if (!isAdmin || !selectedId) return;
    const timer = window.setInterval(() => {
      void refreshVersions();
      void refreshDocuments();
    }, 5000);
    return () => window.clearInterval(timer);
  }, [isAdmin, selectedId, refreshVersions, refreshDocuments]);

  async function act(key: string, operation: () => Promise<unknown>, success: string) {
    setBusyAction(key);
    setError("");
    try {
      await operation();
      await refreshDocuments();
      await refreshVersions();
      onNotice(success);
      return true;
    } catch (cause) {
      setError(errorText(cause));
      return false;
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <div className="workspace documents-workspace">
      <section className="document-list-pane">
        <div className="section-heading"><div><div className="eyebrow">文档目录</div><h1>知识库</h1></div>
          <div className="heading-actions"><button className="icon-button" type="button" title="刷新文档" aria-label="刷新文档"
              onClick={() => void refreshDocuments()}><RefreshCw size={17} /></button>
            {isAdmin && <button className="button primary compact" type="button" onClick={() => setUpload("new")}>
              <Upload size={16} /> 上传
            </button>}</div></div>
        <div className="document-filter"><Search size={16} aria-hidden="true" />
          <label className="sr-only" htmlFor="filter-documents">筛选文档</label>
          <input id="filter-documents" value={filter} onChange={(event) => setFilter(event.target.value)}
            placeholder="筛选文档" /></div>
        <div className="document-table-wrap"><table className="document-table"><thead><tr>
          <th>文档</th><th>范围</th><th>状态</th></tr></thead><tbody>
          {filteredDocuments.map((document) => (
            <tr key={document.id} className={selectedId === document.id ? "selected" : ""}
              onClick={() => selectDocument(document.id)}>
              <td><button type="button" className="table-link" onClick={() => selectDocument(document.id)}>
                <FileText size={16} /> <span>{document.title}</span></button></td>
              <td>{document.department ?? (document.allowed_roles.includes("employee") ? "全员" : "管理员")}</td>
              <td><span className={`status-dot ${document.active_version_id ? "live" : "pending"}`} />
                {document.active_version_id ? "已发布" : "待发布"}</td>
            </tr>
          ))}
          {!filteredDocuments.length && <tr><td colSpan={3} className="table-empty">
            {filter ? "没有匹配的文档" : "暂无可见文档"}</td></tr>}
        </tbody></table></div>
      </section>
      <aside className="document-detail-pane" ref={detailPane}>
        {selected ? <>
          <div className="pane-heading"><div><div className="eyebrow">文档详情</div><h2>{selected.title}</h2></div>
            <span className={`status-pill ${selected.active_version_id ? "active" : "waiting"}`}>
              {selected.active_version_id ? "已发布" : "待发布"}</span></div>
          <dl className="detail-grid">
            <div><dt>可见范围</dt><dd>{selected.department ?? (selected.allowed_roles.includes("employee") ? "所有员工" : "仅管理员")}</dd></div>
            <div><dt>创建时间</dt><dd>{formatDate(selected.created_at)}</dd></div>
          </dl>
          <div className="detail-actions">
            {selected.active_version_id && <button className="button subtle" type="button" onClick={() => onOpenDocument(selected.id)}>
              <ArrowUpRight size={16} /> 打开原文</button>}
            {isAdmin && <><button className="button subtle" type="button" onClick={() => setUpload("replace")}>
              <Upload size={16} /> 替换版本</button>
              <button className="icon-button danger" type="button" title="删除文档" aria-label="删除文档"
                disabled={busyAction !== null} onClick={() => {
                  if (window.confirm(`确定删除“${selected.title}”？删除后员工将无法检索或打开原文。`)) {
                    void act(`delete-${selected.id}`, () => client.remove(token, selected.id), "文档已删除，清理任务已排队。")
                      .then((deleted) => { if (deleted) { setSelectedId(null); setVersions([]); } });
                  }
                }}><Trash2 size={17} /></button></>}
          </div>
          {isAdmin && <div className="versions-section"><div className="subsection-heading"><h3>版本记录</h3>
            <button className="icon-button" type="button" title="刷新版本" aria-label="刷新版本" onClick={() => void refreshVersions()}>
              <RefreshCw size={16} /></button></div>
            <div className="version-list">{versions.map((version) => (
              <div className="version-row" key={version.id}>
                <div className="version-main"><span className="version-number">v{version.version_number}</span>
                  <div><strong>{version.filename}</strong><div className="version-date">
                    上传 {formatDate(version.created_at)}{version.effective_date && ` · 生效 ${version.effective_date}`}
                  </div></div></div>
                <div className="version-tail"><span className={`status-pill ${version.status.toLowerCase()}`}>{statusLabel(version.status)}</span>
                  {version.status === "READY" && <button className="icon-button positive" type="button" title="发布版本" aria-label="发布版本"
                    disabled={busyAction !== null} onClick={() => void act(version.id,
                      () => client.activate(token, selected.id, version.id), "新版本已发布。") }><Check size={17} /></button>}
                  {version.job_status === "FAILED" && version.job_id && <button className="icon-button" type="button"
                    title="重试任务" aria-label="重试任务" disabled={busyAction !== null}
                    onClick={() => void act(version.job_id!, () => client.retry(token, version.job_id!), "任务已重新排队。") }>
                    <RotateCcw size={16} /></button>}
                </div>
                {version.job_error && <p className="version-error">{version.job_error}</p>}
              </div>
            ))}
            {!versions.length && <p className="muted empty-line">暂无版本</p>}
            </div></div>}
        </> : <div className="detail-empty"><Database size={29} strokeWidth={1.6} /><p>选择一份文档查看详情</p></div>}
        {error && <p className="inline-error" role="alert"><AlertCircle size={16} />{error}</p>}
      </aside>
      {upload && <UploadDialog kind={upload} document={selected} token={token} onClose={() => setUpload(null)}
        onSaved={(id) => {
          setUpload(null);
          pendingSelection.current = id;
          void refreshDocuments();
          onNotice("文件已提交，正在等待后台处理。");
        }} />}
    </div>
  );
}

function EvaluationWorkspace({ token }: { token: string }) {
  const [report, setReport] = useState<EvaluationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await client.evaluations(token));
      setError("");
    } catch (cause) {
      setError(errorText(cause));
    } finally {
      setLoading(false);
    }
  }, [token]);
  useEffect(() => { void load(); }, [load]);
  const retrieval = report?.retrieval;
  const generation = report?.generation;
  const issueLabels: Record<string, string> = {
    pending: "待重试", missed_answer: "应答未答", false_answer: "应拒未拒",
    unauthorized: "越权引用", citation: "引用异常",
  };

  return <section className="workspace evaluation-workspace">
    <div className="section-heading"><div><div className="eyebrow">历史离线报告</div><h1>评测结果</h1></div>
      <button className="icon-button" type="button" title="刷新评测" aria-label="刷新评测"
        onClick={() => void load()} disabled={loading}><RefreshCw size={17} /></button></div>
    {error && <p className="inline-error" role="alert"><AlertCircle size={16} />{error}</p>}
    {loading && !report && <p className="evaluation-empty"><RefreshCw className="spin" size={17} /> 正在读取报告</p>}
    {!loading && !retrieval && !generation && <p className="evaluation-empty">暂无评测报告</p>}
    {(retrieval || generation) && <p className="evaluation-provenance">
      虚构制度的离线快照，不随当前知识库自动更新。答案正确率和引用语义支持率尚未独立复核。
    </p>}
    {retrieval && <div className="evaluation-section">
      <div className="subsection-heading"><h3>检索对照</h3>
        <span>{retrieval.document_count ?? "-"} 份文档 · {retrieval.chunk_count ?? "-"} 个片段 · {retrieval.question_count ?? "-"} 题 · {formatDate(retrieval.generated_at)}</span></div>
      <div className="document-table-wrap evaluation-desktop-table"><table className="document-table evaluation-table"><thead><tr>
        <th>方案</th><th>Recall@5</th><th>MRR</th><th>p50</th><th>p95</th><th>越权暴露</th>
      </tr></thead><tbody>
        {retrieval.modes.map((mode) => <tr key={mode.id}>
          <td>{mode.label}</td><td>{mode.recall_at_5?.toFixed(3) ?? "-"}</td>
          <td>{mode.mrr?.toFixed(4) ?? "-"}</td>
          <td>{mode.latency_p50_ms === undefined ? "-" : `${Math.round(mode.latency_p50_ms)} ms`}</td>
          <td>{mode.latency_p95_ms === undefined ? "-" : `${Math.round(mode.latency_p95_ms)} ms`}</td>
          <td>{mode.unauthorized_exposures ?? "-"}</td>
        </tr>)}
      </tbody></table></div>
      <div className="evaluation-mobile-modes">{retrieval.modes.map((mode) => <div className="evaluation-mobile-mode" key={mode.id}>
        <strong>{mode.label}</strong>
        <div className="evaluation-mobile-metrics">
          <span>Recall@5 <b>{mode.recall_at_5?.toFixed(3) ?? "-"}</b></span>
          <span>MRR <b>{mode.mrr?.toFixed(4) ?? "-"}</b></span>
          <span>越权 <b>{mode.unauthorized_exposures ?? "-"}</b></span>
          <span>p50 / p95 <b>{mode.latency_p50_ms === undefined ? "-" : Math.round(mode.latency_p50_ms)} / {mode.latency_p95_ms === undefined ? "-" : Math.round(mode.latency_p95_ms)} ms</b></span>
        </div>
      </div>)}</div>
    </div>}
    {generation && <div className="evaluation-section">
      <div className="subsection-heading"><h3>生成问答</h3>
        <span>{generation.model ?? "未知模型"} · {formatDate(generation.generated_at)}</span></div>
      <div className="evaluation-metrics" aria-label="生成评测指标">
        <div><span>有效结果</span><strong>{generation.completed_count ?? "-"} / {generation.selected_case_count ?? "-"}</strong></div>
        <div><span>有答案题回答</span><strong>{generation.positive_answered ?? "-"} / {generation.positive_evaluated ?? "-"}</strong></div>
        <div><span>无答案题拒答</span><strong>{generation.no_answer_refused ?? "-"} / {generation.no_answer_evaluated ?? "-"}</strong></div>
        <div><span>待重试</span><strong>{generation.pending_count ?? "-"}</strong></div>
      </div>
      <div className="evaluation-detail-line">
        <span>越权暴露 {generation.unauthorized_exposures ?? "-"}</span>
        <span>p50 / p95 {generation.latency_p50_ms === null ? "-" : Math.round(generation.latency_p50_ms)} / {generation.latency_p95_ms === null ? "-" : Math.round(generation.latency_p95_ms)} ms</span>
        <span>输入 / 输出 Token {(generation.input_tokens ?? 0).toLocaleString()} / {(generation.output_tokens ?? 0).toLocaleString()}</span>
      </div>
      <div className="subsection-heading evaluation-issues-heading"><h3>待复核题目</h3><span>{generation.issues.length} 项</span></div>
      <div className="document-table-wrap evaluation-desktop-table"><table className="document-table evaluation-table evaluation-issues"><thead><tr>
        <th>问题</th><th>类别</th><th>状态</th><th>预期文档</th>
      </tr></thead><tbody>
        {generation.issues.map((issue) => <tr key={issue.case_id ?? issue.question}>
          <td>{issue.question}</td><td>{issue.category === "no_answer" ? "无答案" : issue.category === "unauthorized" ? "越权" : issue.category === "cross_document" ? "跨文档" : "单文档"}</td>
          <td><span className={`evaluation-status ${issue.issue_type}`}>{issueLabels[issue.issue_type] ?? issue.status}</span></td>
          <td className="mono">{issue.expected_docs.join(", ") || "-"}</td>
        </tr>)}
        {!generation.issues.length && <tr><td colSpan={4} className="table-empty">暂无待复核题目</td></tr>}
      </tbody></table></div>
      <div className="evaluation-mobile-issues">{generation.issues.map((issue) => <div className="evaluation-mobile-issue" key={issue.case_id ?? issue.question}>
        <div><strong>{issue.question}</strong><span className={`evaluation-status ${issue.issue_type}`}>{issueLabels[issue.issue_type] ?? issue.status}</span></div>
        <small>{issue.category === "no_answer" ? "无答案" : issue.category === "unauthorized" ? "越权" : issue.category === "cross_document" ? "跨文档" : "单文档"} · {issue.expected_docs.join(", ") || "无预期文档"}</small>
      </div>)}
        {!generation.issues.length && <p className="evaluation-empty">暂无待复核题目</p>}
      </div>
    </div>}
  </section>;
}

function AuditWorkspace({ token }: { token: string }) {
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [usage, setUsage] = useState<UsageSummary | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [nextEvents, nextUsage] = await Promise.all([client.audit(token), client.usage(token)]);
      setEvents(nextEvents);
      setUsage(nextUsage);
      setError("");
    }
    catch (cause) { setError(errorText(cause)); }
  }, [token]);
  useEffect(() => { void load(); }, [load]);
  const labels: Record<string, string> = {
    "document.upload": "上传文档", "version.upload": "上传新版本",
    "version.activate": "发布版本", "document.delete": "删除文档", "job.retry": "重试任务",
  };
  const requestLabels: Record<string, string> = {
    answered: "已回答", search_only: "仅检索", insufficient_evidence: "证据不足",
    invalid_citation: "引用无效", model_unavailable: "模型不可用", quota_exceeded: "额度已满",
    reserved: "处理中", settled: "结算中", usage_unconfirmed: "用量未确认",
  };
  return <section className="workspace audit-workspace">
    <div className="section-heading"><div><div className="eyebrow">操作记录</div><h1>审计日志</h1></div>
      <button className="icon-button" type="button" title="刷新审计" aria-label="刷新审计" onClick={() => void load()}>
        <RefreshCw size={17} /></button></div>
    {error && <p className="inline-error" role="alert"><AlertCircle size={16} />{error}</p>}
    {usage && <div className="usage-summary" aria-label="今日模型用量">
      <div><span>UTC 日期</span><strong>{usage.day}</strong></div>
      <div><span>已计入 Token</span><strong>{usage.consumed_tokens.toLocaleString()}</strong></div>
      <div><span>预留 Token</span><strong>{usage.reserved_tokens.toLocaleString()}</strong></div>
      <div><span>剩余额度</span><strong>{usage.remaining_tokens === null ? "不设限" : usage.remaining_tokens.toLocaleString()}</strong></div>
    </div>}
    {usage && <div className="usage-requests">
      <div className="subsection-heading"><h3>最近问答请求</h3></div>
      <div className="document-table-wrap"><table className="document-table usage-table"><thead><tr>
        <th>时间</th><th>状态</th><th>模型</th><th>检索</th><th>生成</th><th>计入 Token</th><th>请求 ID</th>
      </tr></thead><tbody>
        {usage.requests.map((item) => <tr key={item.id}>
          <td>{formatDate(item.created_at)}</td><td title={item.status}>{requestLabels[item.status] ?? item.status}</td><td>{item.model ?? "-"}</td>
          <td>{item.retrieval_ms === null ? "-" : `${Math.round(item.retrieval_ms)} ms`}</td>
          <td>{item.generation_ms === null ? "-" : `${Math.round(item.generation_ms)} ms`}</td>
          <td>{item.charged_tokens.toLocaleString()}</td><td className="mono" title={item.id}>{item.id}</td>
        </tr>)}
        {!usage.requests.length && <tr><td colSpan={7} className="table-empty">暂无请求记录</td></tr>}
      </tbody></table></div>
    </div>}
    <div className="subsection-heading audit-subheading"><h3>文档操作</h3></div>
    <div className="document-table-wrap"><table className="document-table audit-table"><thead><tr>
      <th>时间</th><th>操作</th><th>对象 ID</th><th>结果</th></tr></thead><tbody>
      {events.map((event) => <tr key={event.id}><td>{formatDate(event.created_at)}</td>
        <td>{labels[event.action] ?? event.action}</td><td className="mono">{event.object_id}</td>
        <td>{event.result === "accepted" ? "已接受" : "成功"}</td></tr>)}
      {!events.length && <tr><td colSpan={4} className="table-empty">暂无审计记录</td></tr>}
    </tbody></table></div>
  </section>;
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? "");
  const [user, setUser] = useState<UserProfile | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [view, setView] = useState<View>("chat");
  const [booting, setBooting] = useState(Boolean(token));
  const [notice, setNotice] = useState("");

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setDocuments([]);
    setView("chat");
  }

  useEffect(() => {
    if (!token) { setBooting(false); return; }
    let cancelled = false;
    client.me(token).then((profile) => {
      if (!cancelled) { setUser(profile); setBooting(false); }
    }).catch(() => { if (!cancelled) { logout(); setBooting(false); } });
    return () => { cancelled = true; };
  }, [token]);

  const refreshDocuments = useCallback(async () => {
    if (!token) return;
    try { setDocuments(await client.documents(token)); }
    catch (cause) { setNotice(errorText(cause)); }
  }, [token]);

  useEffect(() => { if (user) void refreshDocuments(); }, [user, refreshDocuments]);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(""), 5000);
    return () => window.clearTimeout(timer);
  }, [notice]);

  async function openDocument(id: string, page?: number | null, versionId?: string) {
    try {
      const blob = await client.source(token, id, versionId);
      const url = URL.createObjectURL(blob);
      const link = window.document.createElement("a");
      link.href = page && blob.type === "application/pdf" ? `${url}#page=${page}` : url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (cause) { setNotice(errorText(cause)); }
  }

  if (booting) return <main className="boot-screen"><RefreshCw className="spin" size={23} /> 正在验证会话</main>;
  if (!token || !user) return <Login onLogin={(nextToken) => {
    sessionStorage.setItem(TOKEN_KEY, nextToken);
    setBooting(true);
    setToken(nextToken);
  }} />;

  return <div className="app-shell">
    <header className="app-header">
      <div className="brand"><span className="brand-icon"><BookOpen size={20} /></span>
        <span><strong>星桥知识库</strong><small>企业制度助手</small></span></div>
      <nav className="main-tabs" aria-label="主导航">
        <button type="button" className={view === "chat" ? "active" : ""} onClick={() => setView("chat")}>
          <Search size={17} /> 问答</button>
        <button type="button" className={view === "documents" ? "active" : ""} onClick={() => setView("documents")}>
          <Database size={17} /> 知识库</button>
        {user.role === "admin" && <button type="button" className={view === "evaluation" ? "active" : ""}
          onClick={() => setView("evaluation")}><BarChart3 size={17} /> 评测</button>}
        {user.role === "admin" && <button type="button" className={view === "audit" ? "active" : ""}
          onClick={() => setView("audit")}><ClipboardList size={17} /> 审计</button>}
      </nav>
      <div className="header-user"><span className="user-role"><Shield size={15} />
        {user.role === "admin" ? "管理员" : user.department ?? "普通员工"}</span>
        <button className="icon-button" type="button" title="退出登录" aria-label="退出登录" onClick={logout}>
          <LogOut size={18} /></button></div>
    </header>
    {view === "chat" && <ChatWorkbench token={token} documents={documents}
      onOpenSource={(source) => void openDocument(source.document_id, source.page_number, source.version_id)} />}
    {view === "documents" && <DocumentWorkspace token={token} user={user} documents={documents}
      refreshDocuments={refreshDocuments} onNotice={setNotice}
      onOpenDocument={(id) => void openDocument(id)} />}
    {view === "evaluation" && user.role === "admin" && <EvaluationWorkspace token={token} />}
    {view === "audit" && user.role === "admin" && <AuditWorkspace token={token} />}
    {notice && <div className="toast" role="status"><AlertCircle size={16} />{notice}
      <button className="icon-button" type="button" title="关闭提示" aria-label="关闭提示" onClick={() => setNotice("")}>
        <X size={15} /></button></div>}
  </div>;
}
