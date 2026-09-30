import assert from "node:assert/strict";
import { mkdir, unlink } from "node:fs/promises";
import path from "node:path";
import { chromium, expect } from "@playwright/test";


const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://127.0.0.1:5173";
const password = process.env.E2E_DEMO_PASSWORD ?? "demo12345";
const outputDir = path.resolve("../.data/demo");
const videoName = path.basename(process.env.DEMO_VIDEO_NAME ?? "local-walkthrough.webm");
const videoPath = path.join(outputDir, videoName);
const verifyLlm = process.env.DEMO_VERIFY_LLM === "1";
const expectTimeout = 40_000;
const pause = (ms = 750) => new Promise((resolve) => setTimeout(resolve, ms));


async function main() {
  await mkdir(outputDir, { recursive: true });
  const browser = await chromium.launch({ channel: process.env.PLAYWRIGHT_CHANNEL ?? "msedge", headless: true, slowMo: 120 });
  try {
  const context = await browser.newContext({
    baseURL,
    viewport: { width: 1440, height: 900 },
    recordVideo: { dir: outputDir, size: { width: 1440, height: 900 } },
  });
  const page = await context.newPage();
  const video = page.video();
  const createdIds = [];
  let adminToken;

  async function login(username) {
    await page.getByLabel("账号").selectOption(username);
    await page.getByLabel("密码").fill(password);
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await page.getByRole("heading", { name: "问答工作台" }).waitFor();
  }

  async function upload(title, filename, content, { department, effectiveDate } = {}) {
    await page.getByRole("button", { name: "知识库" }).click();
    await page.getByRole("button", { name: "上传", exact: true }).click();
    await page.getByLabel("文档标题").fill(title);
    if (department) {
      await page.getByLabel("可见范围").selectOption("department");
      await page.getByLabel("部门名称").fill(department);
    }
    if (effectiveDate) await page.getByLabel("制度生效日期（可选）").fill(effectiveDate);
    await page.getByLabel("文件", { exact: true }).setInputFiles({
      name: filename, mimeType: "text/markdown", buffer: Buffer.from(content, "utf8"),
    });
    const responsePromise = page.waitForResponse((response) =>
      new URL(response.url()).pathname === "/api/v1/documents" && response.request().method() === "POST"
    );
    await page.getByRole("button", { name: "提交处理" }).click();
    const response = await responsePromise;
    assert.equal(response.status(), 202);
    const receipt = await response.json();
    createdIds.push(receipt.document_id);
    await page.getByRole("button", { name: "发布版本" }).waitFor();
    await page.getByRole("button", { name: "发布版本" }).click();
    await page.getByRole("button", { name: "打开原文" }).waitFor();
    await pause();
    return receipt;
  }

  try {
    await page.goto(baseURL);
    await login("admin");
    adminToken = await page.evaluate(() => sessionStorage.getItem("xingqiao-rag-token"));
    assert.ok(adminToken);
    await pause();

    const marker = `XQ-DEMO-${Date.now()}`;
    const title = `差旅审批演示 ${marker}`;
    const first = await upload(title, "travel-v1.md",
      `# 差旅审批演示\n\n## 提交时限\n\n演示标识 ${marker}。国内出差应提前三个工作日提交申请。`,
      { effectiveDate: "2026-10-01" });
    await page.screenshot({ path: path.join(outputDir, "01-upload.png") });

    await page.getByRole("button", { name: "问答", exact: true }).first().click();
    await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "检索" }).click();
    await page.getByLabel("输入问题").fill(`${marker} 国内出差提前多久申请？`);
    await page.getByRole("button", { name: "发送" }).click();
    await expect(page.locator(".source-item").filter({ hasText: marker }).first()).toBeVisible({
      timeout: expectTimeout,
    });
    await pause(1400);
    await page.screenshot({ path: path.join(outputDir, "02-source.png") });

    if (verifyLlm) {
      await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "问答" }).click();
      await page.getByLabel("输入问题").fill("休五天年假最迟提前多久申请？");
      await page.getByRole("button", { name: "发送" }).click();
      const answer = page.locator(".exchange").last();
      await expect(answer.locator(".answer-line > p")).toContainText("两个工作日", {
        timeout: expectTimeout,
      });
      await expect(page.locator(".source-item").first()).toBeVisible({ timeout: expectTimeout });
      await pause(1400);
      await page.screenshot({ path: path.join(outputDir, "03-answer.png") });
    }

    await page.getByRole("button", { name: "知识库" }).click();
    await page.getByRole("button", { name: title }).click();
    await page.getByRole("button", { name: "替换版本" }).click();
    await page.getByLabel("制度生效日期（可选）").fill("2026-11-01");
    await page.getByLabel("文件", { exact: true }).setInputFiles({
      name: "travel-v2.md", mimeType: "text/markdown",
      buffer: Buffer.from(`# 差旅审批演示\n\n## 提交时限\n\n演示标识 ${marker}。国内出差应提前五个工作日提交申请。`, "utf8"),
    });
    await page.getByRole("button", { name: "提交处理" }).click();
    const versionRow = page.locator(".version-row").filter({ hasText: "travel-v2.md" });
    await versionRow.getByRole("button", { name: "发布版本" }).waitFor();
    await versionRow.getByRole("button", { name: "发布版本" }).click();
    await expect(versionRow).toContainText("生效 2026-11-01");
    await pause(1200);
    await page.screenshot({ path: path.join(outputDir, "03-replacement.png") });

    const restrictedMarker = `XQ-ACL-${Date.now()}`;
    const restrictedTitle = `采购权限演示 ${restrictedMarker}`;
    await upload(restrictedTitle, "procurement.md",
      `# 采购权限演示\n\n## 专属规则\n\n演示标识 ${restrictedMarker}。供应商准入须由采购部复核。`,
      { department: "采购部" });
    await page.getByRole("button", { name: "退出登录" }).click();
    await login("employee");
    await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "检索" }).click();
    await page.getByLabel("输入问题").fill(restrictedMarker);
    await page.getByRole("button", { name: "发送" }).click();
    await page.locator(".exchange").last().waitFor();
    await expect(page.locator(".source-item").filter({ hasText: restrictedMarker })).toHaveCount(0);
    await pause(1000);
    await page.screenshot({ path: path.join(outputDir, "04-unauthorized.png") });

    await page.getByRole("button", { name: "退出登录" }).click();
    await login("procurement");
    await page.getByRole("group", { name: "查询模式" }).getByRole("button", { name: "检索" }).click();
    await page.getByLabel("输入问题").fill(restrictedMarker);
    await page.getByRole("button", { name: "发送" }).click();
    await expect(page.locator(".source-item").filter({ hasText: restrictedMarker }).first()).toBeVisible({
      timeout: expectTimeout,
    });
    await pause(1200);
    await page.screenshot({ path: path.join(outputDir, "05-authorized.png") });

    await page.getByRole("button", { name: "退出登录" }).click();
    await login("admin");
    await page.getByRole("button", { name: "知识库" }).click();
    await page.getByRole("button", { name: title }).click();
    page.once("dialog", (dialog) => void dialog.accept());
    await page.getByRole("button", { name: "删除文档" }).click();
    await expect(page.getByRole("button", { name: title })).toHaveCount(0);
    await pause(1000);

    await page.getByRole("button", { name: "评测" }).click();
    await page.getByRole("heading", { name: "评测结果" }).waitFor();
    await page.locator(".evaluation-section .evaluation-table tbody tr").first().waitFor();
    await pause(1600);
    await page.screenshot({ path: path.join(outputDir, "06-evaluation.png") });

    const oldSource = await page.request.get(`/api/v1/documents/${first.document_id}/source`, {
      headers: { Authorization: `Bearer ${adminToken}` }, params: { version_id: first.version_id },
    });
    assert.equal(oldSource.status(), 404);
  } finally {
    if (adminToken) {
      for (const id of createdIds) {
        await page.request.delete(`/api/v1/documents/${id}`, {
          headers: { Authorization: `Bearer ${adminToken}` },
        }).catch(() => undefined);
      }
    }
    await context.close();
    if (video) {
      const rawVideoPath = await video.path();
      await video.saveAs(videoPath);
      if (rawVideoPath !== videoPath) await unlink(rawVideoPath);
    }
  }
  console.log(`Demo recording: ${videoPath}`);
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
