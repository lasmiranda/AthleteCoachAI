const { test, expect } = require("@playwright/test");

test("all six real screens load without browser errors or external connections", async ({ page }) => {
  const errors = [];
  const external = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => {
    if (!request.url().startsWith("http://127.0.0.1:8765")) external.push(request.url());
  });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /A good day starts/ })).toBeVisible();
  await expect(page.locator(".mission .pill").first()).toHaveText("BUILD");
  await expect(page.locator(".metric").first()).toContainText("1,200");
  for (const [hash, heading] of [
    ["dashboard", "The response behind the routine."],
    ["goal", "Define the finish line. Protect the journey."],
    ["plan", "A plan that listens, not just pushes."],
    ["wins", "Small wins. Smarter training."],
    ["coach", "Your data, explained like a teammate."],
  ]) {
    await page.locator(`nav a[href="#${hash}"]`).click();
    await expect(page.getByRole("heading", { name: heading, exact: true })).toBeVisible();
  }
  await page.getByRole("button", { name: "Explain my load" }).click();
  await expect(page.locator(".coach-bubble").last()).toContainText("1200 AU");
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});

test("goal, check-in and plan edits survive a real page reload", async ({ page }) => {
  await page.goto("/#goal");
  await expect(page.locator("#goal-form")).toBeVisible();
  await page.locator('[name="goal_type"]').selectOption("10K");
  await page.locator('[name="target_time_min"]').fill("52");
  await page.locator('[name="secondary"]').fill("Make recovery count");
  await page.getByRole("button", { name: "Save my goal" }).click();
  await expect(page.getByRole("status")).toContainText("Goal saved");
  await page.reload();
  await expect(page.locator('[name="goal_type"]')).toHaveValue("10K");
  await expect(page.locator('[name="target_time_min"]')).toHaveValue("52");
  await page.locator('nav a[href="#plan"]').click();
  await page.locator('#plan-form [name="duration_min"]').fill("50");
  await page.getByRole("button", { name: "Save session", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Plan session saved");
  await page.reload();
  await expect(page.locator('#plan-form [name="duration_min"]')).toHaveValue("50");
  await page.locator('nav a[href="#today"]').click();
  await page.locator('#checkin-form [name="sleep_hours"]').fill("8.5");
  await page.getByRole("button", { name: "Save check-in & recalculate" }).click();
  await expect(page.getByRole("status")).toContainText("Check-in saved");
  await page.reload();
  await expect(page.locator('#checkin-form [name="sleep_hours"]')).toHaveValue("8.5");
});

test("protective recommendation earns only verified accepted/completed wins", async ({ page }) => {
  await page.goto("/");
  await page.locator("#athlete-select").selectOption("demo-sam");
  await expect(page.locator(".mission .pill").first()).toHaveText("PROTECT");
  await expect(page.locator(".mission")).toContainText("18");
  await page.getByRole("button", { name: /Accept recovery adjustment/ }).click();
  await expect(page.getByRole("status")).toContainText("Smart Training win verified");
  await page.getByRole("button", { name: /Log actual session/ }).click();
  await expect(page.locator("#log-dialog")).toBeVisible();
  await page.locator('#complete-form input[type="checkbox"]').check();
  await page.getByRole("button", { name: "Save actual session", exact: true }).click();
  await expect(page.locator(".mission")).toContainText("Today's session is recorded.");
  await page.locator('nav a[href="#wins"]').click();
  await expect(page.locator(".win-card[data-earned]").filter({ hasText: "Recovery Win" })).toBeVisible();
  await expect(page.locator(".win-card[data-earned]").filter({ hasText: "Smart Training" })).toBeVisible();
  await page.reload();
  await expect(page.locator("#athlete-select")).toHaveValue("demo-sam");
  await expect(page.locator(".win-card[data-earned]").filter({ hasText: "Recovery Win" })).toBeVisible();
});

test("CSV validation is atomic, provenance updates, and imports persist", async ({ page, request }) => {
  await page.goto("/");
  await page.locator("#athlete-select").selectOption("demo-new");
  await expect(page.locator(".mission .pill").first()).toHaveText("INSUFFICIENT");
  await page.getByRole("button", { name: /Data studio/ }).click();
  await page.locator("#csv-file").setInputFiles({ name: "bad.csv", mimeType: "text/csv", buffer: Buffer.from("bad,header\n1,2") });
  await page.locator("#confirm-import").check();
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.locator("#import-error")).toContainText("header");
  let response = await request.get("/api/athletes/demo-new");
  expect((await response.json()).athlete.records).toHaveLength(0);
  response = await request.get("/api/athletes/demo-alex/export");
  const csv = (await response.text()).replaceAll("demo-alex", "demo-new");
  await page.locator("#csv-file").setInputFiles({ name: "normalized.csv", mimeType: "text/csv", buffer: Buffer.from(csv) });
  await page.getByRole("button", { name: "Validate & import" }).click();
  await expect(page.getByRole("status")).toContainText("CSV validated and saved");
  await expect(page.locator("#data-provenance")).toContainText("CSV import");
  await page.getByRole("button", { name: "Close data studio" }).click();
  await expect(page.locator(".mission .pill").first()).toHaveText("BUILD");
  await page.reload();
  await expect(page.locator("#athlete-select")).toHaveValue("demo-new");
  await expect(page.locator(".mission .pill").first()).toHaveText("BUILD");
  response = await request.get("/api/athletes/demo-new");
  expect((await response.json()).athlete.records).toHaveLength(35);
});

test("mobile navigation and actual-session form fit without page overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /A good day starts/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('nav a[href="#plan"]').click();
  await expect(page.locator("#plan-form")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.locator('nav a[href="#today"]').click();
  await page.getByRole("button", { name: /Log actual session/ }).click();
  await expect(page.locator("#log-dialog")).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
});

test("backend connection errors are visible rather than fallback metrics", async ({ page }) => {
  await page.route("**/api/athletes/demo-alex", route => route.fulfill({
    status: 500, contentType: "application/json", body: JSON.stringify({ error: "Test unavailable local data" }),
  }));
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("Test unavailable local data");
  await expect(page.getByRole("heading", { name: /couldn't reach your local coach/ })).toBeVisible();
  await expect(page.locator(".metric")).toHaveCount(0);
  await page.unroute("**/api/athletes/demo-alex");
  await page.getByRole("button", { name: "Retry connection" }).click();
  await expect(page.getByRole("heading", { name: /A good day starts/ })).toBeVisible();
});

test("dashboard, plan and coach share provisional explanations and scoped references", async ({ page, request }) => {
  const before = await (await request.get("/api/athletes/demo-alex/decisions")).json();
  await page.goto("/#dashboard");
  for (const hash of ["dashboard", "plan", "coach"]) {
    await page.locator(`nav a[href="#${hash}"]`).click();
    await expect(page.locator(".decision-basis")).toContainText("demo-rules-v3");
    await expect(page.locator(".decision-basis")).toContainText("PROVISIONAL DECISION");
    await expect(page.locator(".baseline-quality")).toContainText("comparability");
    await expect(page.locator(".evidence-panel")).toContainText("No calibrated confidence percentage");
    const rule = page.locator(".evidence-rule").filter({ has: page.getByText("HRV percentage-change flag", { exact: true }) });
    await rule.locator("summary").first().click();
    await expect(rule.locator("dd").filter({ hasText: "not a universal" })).toBeVisible();
    await expect(rule.locator('a[href="https://pmc.ncbi.nlm.nih.gov/articles/PMC3936188/"]').first()).toBeVisible();
  }
  await page.getByRole("button", { name: "Why this readiness?", exact: true }).click();
  await expect(page.locator(".coach-bubble").last()).toContainText("comparability");
  await expect(page.locator(".coach-meta").last()).toContainText("demo-rules-v3");
  const after = await (await request.get("/api/athletes/demo-alex/decisions")).json();
  expect(after).toEqual(before);
});

test("Today, Dashboard, Plan and Coach show the same fact-context-criterion-action review", async ({ page, request }) => {
  const v = await (await request.get("/api/athletes/demo-sam")).json();
  const review = v.prediction.monitoring_review;
  await page.goto("/?athlete=demo-sam");
  for (const hash of ["today", "dashboard", "plan", "coach"]) {
    await page.locator(`nav a[href="#${hash}"]`).click();
    const panel = page.locator(".decision-basis");
    await expect(panel).toContainText(review.summary);
    await expect(panel).toContainText(review.review_action);
    await expect(panel).toContainText("1. Observed facts");
    await expect(panel).toContainText("2. Source-supported monitoring context");
    await expect(panel).toContainText("3. Provisional decision criterion");
    await expect(panel).toContainText("4. Suggested review / action");
    await expect(panel).toContainText("Training can produce adaptation");
    await expect(panel.locator('a[href="https://pmc.ncbi.nlm.nih.gov/articles/PMC7534938/"]').last()).toBeVisible();
  }
  await page.getByRole("button", { name: "Review load and recovery", exact: true }).click();
  await expect(page.locator(".coach-bubble").last()).toContainText(review.summary);
  await page.goto("/?athlete=demo-new#dashboard");
  await expect(page.locator(".decision-basis")).toContainText("incomplete");
  await expect(page.locator(".decision-basis")).toContainText("(unavailable)");
});

test("saved decisions retain original outputs across edits and reloads", async ({ page, request }) => {
  const before = await (await request.get("/api/athletes/demo-alex")).json();
  await page.goto("/#plan");
  await page.getByRole("button", { name: "Save current decision snapshot" }).click();
  await expect(page.getByRole("status")).toContainText("Decision snapshot saved");
  const saved = await (await request.get("/api/athletes/demo-alex/decisions")).json();
  const snapshot = saved.snapshots.at(-1);
  expect(snapshot.features).toEqual(before.features);
  expect(snapshot.prediction).toEqual(before.prediction);
  expect(snapshot.evidence_manifest.rule_version).toBe("demo-rules-v3");
  expect(snapshot.input_digest).toMatch(/^[a-f0-9]{64}$/);
  await page.locator('#plan-form [name="duration_min"]').fill("48");
  await page.getByRole("button", { name: "Save session", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Plan session saved");
  await page.reload();
  await expect(page.locator(".decision-history")).toContainText(snapshot.id.slice(0, 8));
  const after = await (await request.get("/api/athletes/demo-alex/decisions")).json();
  expect(after.snapshots.find(s => s.id === snapshot.id)).toEqual(snapshot);
  expect(after.snapshots).toHaveLength(saved.snapshots.length + 1);
});

test("measurement declarations validate atomically and show honest insufficient comparability", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.locator("#checkin-form")).toBeVisible();
  await page.locator(".metadata-form summary").click();
  await page.locator('[name="hrv_ms"]').fill("70");
  await page.locator('[name="hrv_device"]').fill("demo-device-A");
  const before = await (await request.get("/api/athletes/demo-alex/decisions")).json();
  await page.getByRole("button", { name: "Save check-in & recalculate" }).click();
  await expect(page.locator("#checkin-form .form-error")).toContainText("must be supplied together");
  expect(await (await request.get("/api/athletes/demo-alex/decisions")).json()).toEqual(before);
  await page.locator('[name="hrv_protocol"]').fill("RMSSD; morning; seated");
  await page.getByRole("button", { name: "Save check-in & recalculate" }).click();
  await expect(page.getByRole("status")).toContainText("Check-in saved");
  await page.locator('nav a[href="#dashboard"]').click();
  await expect(page.locator(".baseline-card").first()).toContainText("0/28 observations used");
  await expect(page.locator(".baseline-card").first()).toContainText("insufficient-history");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  const exported = await (await request.get("/api/athletes/demo-alex/export")).text();
  expect(exported).toContain("hrv_device,hrv_protocol,resting_hr_device,resting_hr_protocol");
  expect(exported).toContain("demo-device-A,RMSSD; morning; seated");
});
