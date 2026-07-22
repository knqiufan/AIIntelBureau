import { expect, test } from "@playwright/test";

test("separate passcodes create cookie-backed operator and read-only stage sessions", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "输入活动口令" })).toBeVisible();
  await page.getByLabel("活动口令").fill("e2e-activity-key");
  await page.getByRole("button", { name: "进入演示" }).click();
  await expect(page.getByText("先加载一份任务")).toBeVisible();

  const caseId = page.url().split("/").pop();
  const stage = await context.newPage();
  await stage.goto(`/stage/${caseId}`);
  await expect(stage.getByRole("heading", { name: "输入活动口令" })).toBeVisible();
  await stage.getByLabel("活动口令").fill("e2e-stage-key");
  const stageSnapshotResponse = stage.waitForResponse((response) => response.url().includes("/stage-snapshot") && response.status() === 200);
  await stage.getByRole("button", { name: "进入演示" }).click();
  const stageSnapshot = await (await stageSnapshotResponse).text();
  expect(stageSnapshot).not.toContain("保险箱密码是 0427");
  expect(stageSnapshot).not.toContain("source_memory_id");
  await expect(stage.getByText("每个角色都有自己的私有记忆空间")).toBeVisible();

  await page.getByRole("button", { name: /保险箱密码/ }).click();
  await expect(stage.locator(".stage-role.role-informant strong")).toHaveText(/1/, { timeout: 5000 });
  await expect(stage.getByText("保险箱密码是 0427")).toHaveCount(0);
});
