import { expect, test } from "@playwright/test";

const password = process.env.E2E_DEMO_PASSWORD ?? "demo12345";

async function login(page: import("@playwright/test").Page, username: string) {
  await page.goto("/");
  await page.getByLabel("账号").selectOption(username);
  await page.getByLabel("密码").fill(password);
  await page.getByRole("button", { name: "登录", exact: true }).click();
  await expect(page.getByRole("heading", { name: "问答工作台" })).toBeVisible();
}

test("admin uploads, publishes, searches, and deletes a document", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, "admin");
  await page.getByRole("button", { name: "知识库" }).click();
  await page.getByRole("button", { name: "上传", exact: true }).click();

  const title = `浏览器回归制度 ${Date.now()}`;
  await page.getByLabel("文档标题").fill(title);
  await page.getByLabel("制度生效日期（可选）").fill("2026-10-01");
  await page.getByLabel("文件", { exact: true }).setInputFiles({
    name: "browser-policy.md",
    mimeType: "text/markdown",
    buffer: Buffer.from("# Browser policy\n\n## Travel\n\n出差申请应提前三个工作日提交。", "utf8"),
  });
  await page.getByRole("button", { name: "提交处理" }).click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "发布版本" })).toBeVisible();
  await expect(page.locator(".version-row").first()).toContainText("生效 2026-10-01");
  await page.getByRole("button", { name: "发布版本" }).click();
  await expect(page.getByRole("button", { name: "打开原文" })).toBeVisible();

  await page.getByRole("button", { name: "问答", exact: true }).first().click();
  await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "检索" }).click();
  await page.getByLabel("输入问题").fill("出差申请应提前多久提交？");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.getByText("找到", { exact: false }).first()).toBeVisible();
  await expect(page.locator(".source-item").first()).toContainText("三个工作日");
  const popupPromise = page.waitForEvent("popup", { timeout: 10_000 });
  await page.locator(".source-item").first().getByRole("button", { name: "打开原文" }).click();
  const sourcePopup = await popupPromise;
  expect(sourcePopup.url()).toContain("blob:");
  await sourcePopup.close();
  await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "问答" }).click();
  await page.getByLabel("输入问题").fill("出差申请应提前多久提交？");
  await page.getByRole("button", { name: "发送" }).click();
  await expect(page.locator(".exchange")).toHaveCount(2);
  await expect(page.locator(".exchange").last().locator(".answer-line > p")).toBeVisible();
  await page.screenshot({ path: "test-results/desktop.png", fullPage: true });

  await page.getByRole("button", { name: "审计" }).click();
  await expect(page.getByRole("heading", { name: "最近问答请求" })).toBeVisible();
  await expect(page.locator(".usage-table tbody tr").first()).toBeVisible();
  await page.screenshot({ path: "test-results/usage.png", fullPage: true });

  await page.getByRole("button", { name: "知识库" }).click();
  await page.getByRole("button", { name: title }).click();
  page.once("dialog", (dialog) => void dialog.accept());
  await page.getByRole("button", { name: "删除文档" }).click();
  await expect(page.getByRole("button", { name: title })).toHaveCount(0);
});

test("replacing a published document hides the old version and revokes its source", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, "admin");
  const token = await page.evaluate(() => sessionStorage.getItem("xingqiao-rag-token"));
  expect(token).toBeTruthy();
  const headers = { Authorization: `Bearer ${token}` };
  const suffix = Date.now();
  const title = `版本隔离回归 ${suffix}`;
  const oldMarker = `XQ-OLD-${suffix}`;
  const newMarker = `XQ-NEW-${suffix}`;
  let documentId: string | undefined;

  try {
    await page.getByRole("button", { name: "知识库" }).click();
    await page.getByRole("button", { name: "上传", exact: true }).click();
    await page.getByLabel("文档标题").fill(title);
    await page.getByLabel("文件", { exact: true }).setInputFiles({
      name: "replacement-v1.md", mimeType: "text/markdown",
      buffer: Buffer.from(`# 版本隔离\n\n## 当前规则\n\n唯一校验码为 ${oldMarker}。`, "utf8"),
    });
    const firstUpload = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/v1/documents" && response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "提交处理" }).click();
    documentId = (await (await firstUpload).json()).document_id;
    await expect(page.getByRole("button", { name: "发布版本" })).toBeVisible();
    await page.getByRole("button", { name: "发布版本" }).click();

    const oldSearch = await page.request.post("/api/v1/search", {
      headers, data: { query: oldMarker, limit: 6 },
    });
    expect(oldSearch.ok()).toBe(true);
    const oldHits = await oldSearch.json();
    expect(oldHits.some((hit: { document_id: string; text: string }) =>
      hit.document_id === documentId && hit.text.includes(oldMarker)
    )).toBe(true);
    const oldVersionId = oldHits.find((hit: { document_id: string }) => hit.document_id === documentId)?.version_id;
    expect(oldVersionId).toBeTruthy();

    await page.getByRole("button", { name: "替换版本" }).click();
    await page.getByLabel("文件", { exact: true }).setInputFiles({
      name: "replacement-v2.md", mimeType: "text/markdown",
      buffer: Buffer.from(`# 版本隔离\n\n## 当前规则\n\n唯一校验码为 ${newMarker}。`, "utf8"),
    });
    const secondUpload = page.waitForResponse((response) =>
      new URL(response.url()).pathname === `/api/v1/documents/${documentId}/versions`
      && response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "提交处理" }).click();
    const nextVersionId = (await (await secondUpload).json()).version_id;
    const newRow = page.locator(".version-row").filter({ hasText: "replacement-v2.md" });
    await expect(newRow.getByRole("button", { name: "发布版本" })).toBeVisible();
    await newRow.getByRole("button", { name: "发布版本" }).click();
    await expect(newRow).toContainText("已发布");

    const newSearch = await page.request.post("/api/v1/search", {
      headers, data: { query: newMarker, limit: 6 },
    });
    expect(newSearch.ok()).toBe(true);
    const newHits = await newSearch.json();
    expect(newHits.some((hit: { document_id: string; version_id: string; text: string }) =>
      hit.document_id === documentId && hit.version_id === nextVersionId && hit.text.includes(newMarker)
    )).toBe(true);
    expect(newHits.some((hit: { document_id: string; text: string }) =>
      hit.document_id === documentId && hit.text.includes(oldMarker)
    )).toBe(false);

    const outdatedSource = await page.request.get(`/api/v1/documents/${documentId}/source`, {
      headers, params: { version_id: oldVersionId },
    });
    expect(outdatedSource.status()).toBe(404);
    const currentVersionSource = await page.request.get(`/api/v1/documents/${documentId}/source`, {
      headers, params: { version_id: nextVersionId },
    });
    expect(currentVersionSource.ok()).toBe(true);
    expect(await currentVersionSource.text()).toContain(newMarker);

    const source = await page.request.get(`/api/v1/documents/${documentId}/source`, { headers });
    expect(source.ok()).toBe(true);
    const sourceText = await source.text();
    expect(sourceText).toContain(newMarker);
    expect(sourceText).not.toContain(oldMarker);
    page.once("dialog", (dialog) => void dialog.accept());
    await page.getByRole("button", { name: "删除文档" }).click();
    await expect(page.getByRole("button", { name: title })).toHaveCount(0);
    const deletedSource = await page.request.get(`/api/v1/documents/${documentId}/source`, { headers });
    expect(deletedSource.status()).toBe(404);
    const deletedSearch = await page.request.post("/api/v1/search", {
      headers, data: { query: newMarker, limit: 6 },
    });
    expect(deletedSearch.ok()).toBe(true);
    expect((await deletedSearch.json()).some((hit: { document_id: string }) =>
      hit.document_id === documentId
    )).toBe(false);
  } finally {
    if (documentId) {
      await page.request.delete(`/api/v1/documents/${documentId}`, { headers }).catch(() => undefined);
    }
  }
});

test("admin evaluation snapshot is readable on desktop and mobile", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await login(page, "admin");
  await page.getByRole("button", { name: "评测" }).click();
  await expect(page.getByRole("heading", { name: "评测结果" })).toBeVisible();
  await expect(page.locator(".evaluation-table tbody tr").first()).toContainText("Dense");
  await expect(page.getByRole("heading", { name: "待复核题目" })).toBeVisible();
  await expect(page.locator(".evaluation-status").first()).toBeVisible();
  await page.screenshot({ path: "test-results/evaluation-desktop.png", fullPage: true });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "test-results/evaluation-mobile.png", fullPage: true });
  const header = await page.locator(".app-header").boundingBox();
  const heading = await page.locator(".section-heading").boundingBox();
  expect(header).not.toBeNull();
  expect(heading).not.toBeNull();
  expect(heading!.y).toBeGreaterThanOrEqual(header!.y + header!.height);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
});

test("admin upload form keeps its date field usable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "admin");
  await page.getByRole("button", { name: "知识库" }).click();
  await page.getByRole("button", { name: "上传", exact: true }).click();
  await expect(page.getByLabel("制度生效日期（可选）")).toBeVisible();
  await page.getByLabel("制度生效日期（可选）").fill("2026-10-01");
  await expect(page.getByRole("button", { name: "提交处理" })).toBeVisible();
  const dialog = await page.getByRole("dialog").boundingBox();
  expect(dialog).not.toBeNull();
  expect(dialog!.x).toBeGreaterThanOrEqual(0);
  expect(dialog!.x + dialog!.width).toBeLessThanOrEqual(390);
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(false);
  await page.screenshot({ path: "test-results/upload-mobile.png", fullPage: true });
});

test("employee mobile workspace has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "employee");
  await expect(page.getByRole("button", { name: "审计" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "评测" })).toHaveCount(0);
  await page.screenshot({ path: "test-results/mobile-chat.png", fullPage: true });
  await page.getByRole("button", { name: "知识库" }).click();
  await expect(page.getByRole("heading", { name: "知识库" })).toBeVisible();
  await page.getByLabel("筛选文档").fill("年休假");
  await expect(page.getByRole("button", { name: "年休假与请假办法" })).toBeVisible();
  await page.getByRole("button", { name: "年休假与请假办法" }).click();
  await expect(page.locator(".document-detail-pane").getByRole("heading", { name: "年休假与请假办法" })).toBeVisible();
  const header = await page.locator(".app-header").boundingBox();
  const heading = await page.locator(".section-heading").boundingBox();
  expect(header).not.toBeNull();
  expect(heading).not.toBeNull();
  expect(heading!.y).toBeGreaterThanOrEqual(header!.y + header!.height);
  await page.screenshot({ path: "test-results/mobile.png", fullPage: true });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
});
