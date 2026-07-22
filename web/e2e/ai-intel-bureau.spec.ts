import { expect, test, type Page } from "@playwright/test";

async function loadPassword(page: Page): Promise<void> {
  await page.goto("/");
  await expect(page.getByText("先加载一份任务")).toBeVisible();
  await page.getByRole("button", { name: /A · 保险箱密码/ }).click();
  await expect(page.getByText("保险箱密码是 0427").first()).toBeVisible();
}

test("loads the password fixture with three locked cards", async ({ page }) => {
  await loadPassword(page);
  await expect(page.getByText("锁定私有")).toHaveCount(3);
});

test("detective sees an explicit empty retrieval before publication", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(page.getByText("未命中可见记忆").first()).toBeVisible();
  await expect(page.getByText("不知道").first()).toBeVisible();
  await expect(page.getByText("我不知道；当前可见记忆中没有这方面的情报。")).toHaveCount(0);
});

test("informant sees its private password card", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: /线人/ }).first().click();
  await page.getByRole("button", { name: "问线人密码" }).click();
  await expect(page.getByText("根据当前可见情报：保险箱密码是 0427")).toBeVisible();
});

test("publication retains source and inserts a public copy", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: /线人/ }).first().click();
  await page.getByRole("button", { name: /保险箱密码是 0427/ }).click();
  await page.getByRole("button", { name: "公开到公告板" }).click();
  await expect(page.getByText("公开副本")).toBeVisible();
  await expect(page.getByText("私有原件")).toHaveCount(3);
});

test("detective learns only from the bulletin board after publication", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: /线人/ }).first().click();
  await page.getByRole("button", { name: /保险箱密码是 0427/ }).click();
  await page.getByRole("button", { name: "公开到公告板" }).click();
  await page.getByRole("button", { name: /侦探/ }).first().click();
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(page.getByText("已基于可见证据作答")).toBeVisible();
  await expect(page.getByText("公告板").last()).toBeVisible();
});

test("four-step guide follows the evidence flow and recovers from event replay after refresh", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await page.getByRole("button", { name: /线人/ }).first().click();
  await page.getByRole("button", { name: "问线人密码" }).click();
  await page.getByRole("button", { name: /保险箱密码是 0427/ }).click();
  await page.getByRole("button", { name: "公开到公告板" }).click();
  await page.getByRole("button", { name: /侦探/ }).first().click();
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(page.getByText("演示完成")).toBeVisible();

  await page.reload();
  await expect(page.getByText("演示完成")).toBeVisible({ timeout: 5000 });
});

test("captures 1440x900 and 1920x1080 operation views without horizontal overflow", async ({ page }, testInfo) => {
  for (const viewport of [{ width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    await loadPassword(page);
    expect(await page.locator("html").evaluate((element) => element.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({ path: testInfo.outputPath(`operate-${viewport.width}x${viewport.height}.png`), fullPage: true });
  }
});

test("reset clears only the active case and returns to the task picker", async ({ page }) => {
  await loadPassword(page);
  await page.getByRole("button", { name: "重置当前案" }).click();
  await expect(page.getByText("先加载一份任务")).toBeVisible();
  await expect(page.getByText("暂无记忆")).toHaveCount(4);
});

test("stage is read-only and can recover the same case snapshot", async ({ page, context }) => {
  await loadPassword(page);
  const caseId = page.url().split("/").pop();
  const stage = await context.newPage();
  await stage.goto(`/stage/${caseId}`);
  await expect(stage.getByText("私有记忆默认隔离；共享必须显式发生")).toBeVisible();
  await expect(stage.getByRole("button", { name: "新开案件" })).toHaveCount(0);
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(stage.getByRole("heading", { name: "本次操作没有命中已公开情报" })).toBeVisible({ timeout: 5000 });
});
