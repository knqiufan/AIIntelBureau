import { expect, test } from "@playwright/test";

test("an activity passcode creates a cookie-backed operator and stage session", async ({ page, context }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "输入活动口令" })).toBeVisible();
  await page.getByLabel("活动口令").fill("e2e-activity-key");
  await page.getByRole("button", { name: "进入演示" }).click();
  await expect(page.getByText("先加载一份任务")).toBeVisible();

  const caseId = page.url().split("/").pop();
  const stage = await context.newPage();
  await stage.goto(`/stage/${caseId}`);
  await expect(stage.getByText("每个角色都有自己的私有记忆空间")).toBeVisible();
  await expect(stage.getByRole("heading", { name: "输入活动口令" })).toHaveCount(0);

  await page.getByRole("button", { name: /保险箱密码/ }).click();
  await expect(stage.locator(".stage-role.role-informant strong")).toHaveText(/1/, { timeout: 5000 });
});
