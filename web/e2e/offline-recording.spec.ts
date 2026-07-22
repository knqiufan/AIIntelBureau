import { expect, test } from "@playwright/test";

test("offline recording: password isolation four-act flow", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByText("先加载一份任务")).toBeVisible();
  await page.waitForTimeout(500);
  await page.getByRole("button", { name: /A · 保险箱密码/ }).click();
  await expect(page.getByText("保险箱密码是 0427").first()).toBeVisible();
  await page.waitForTimeout(700);

  const caseId = page.url().split("/").pop();
  const stage = await context.newPage();
  await stage.goto(`/stage/${caseId}`);
  await expect(stage.getByText("私有记忆默认隔离；共享必须显式发生")).toBeVisible();

  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(page.getByText("未命中可见记忆").first()).toBeVisible();
  await page.waitForTimeout(700);

  await page.getByRole("button", { name: /线人/ }).first().click();
  await page.getByRole("button", { name: "问线人密码" }).click();
  await expect(page.getByText("根据当前可见情报：保险箱密码是 0427")).toBeVisible();
  await page.waitForTimeout(700);

  await page.getByRole("button", { name: /保险箱密码是 0427/ }).click();
  const publish = page.getByRole("button", { name: "公开到公告板" });
  await expect(publish).toBeEnabled();
  // The recording keeps a second, continuously repainting stage page open; use
  // the already-asserted enabled control to avoid a transient overlay retry.
  await publish.click({ force: true });
  await expect(page.getByText("公开副本")).toBeVisible();
  await page.waitForTimeout(700);

  await page.getByRole("button", { name: /侦探/ }).first().click();
  await page.getByRole("button", { name: "问侦探密码" }).click();
  await expect(page.getByText("演示完成")).toBeVisible();
  await expect(stage.getByText("公告板").last()).toBeVisible();
  await page.waitForTimeout(1200);
});
