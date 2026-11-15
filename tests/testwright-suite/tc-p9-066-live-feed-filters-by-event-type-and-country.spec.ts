import { test, expect } from '@playwright/test';

// Grounded on the live realtime-analytics page (2026-11-15). The live feed
// ([data-wt="ra-feed"]) has a filter bar (.flex-wrap) of pills that are DERIVED
// FROM THE DATA currently in the window:
//   • "All" — always present; clears the active filter.
//   • event-type pills (lowercase_with_underscores: session_start, run_success,
//     page_view, run_error, …) — one per event type present. Always ≥1.
//   • country pills (two uppercase letters: IN, US, …) — one per country present,
//     and rendered ONLY when the window holds 2+ countries. On a single-country
//     window (common — the traffic is mostly one geo) NO country pill shows.
// Clicking a type pill narrows the feed to that type; clicking a country pill
// narrows to that country; "All" resets. Each feed row's first <span> is its
// event type and a 2-letter <span> is its country.
//
// Because the pills are data-driven, this spec derives its targets from the feed
// itself and asserts the count-agnostic PROPERTY "every visible row matches the
// active filter" (stable under live inserts — a non-matching event is never
// shown). Country filtering is exercised when a country pill exists; when the
// window is single-country the control is legitimately absent, so the spec
// instead asserts the feed is consistently single-country. Hardcoding a country
// pill would false-red whenever live traffic happens to be one geo.
const BASE_URL = 'https://ml-portfolio-rho.vercel.app/tools/realtime-analytics';

type Row = { type: string; country: string };

test('Live feed filters by event type and country, and All resets', async ({ page }) => {
  // Generous budget: under a full-suite batch the shared Vercel/Supabase backend
  // serves dozens of concurrent page loads, so the live feed can take tens of
  // seconds to populate. Alone the page is ~2s; this headroom is only ever spent
  // under that contention.
  test.setTimeout(120000);
  await page.goto(BASE_URL, { waitUntil: 'domcontentloaded' });

  const feed = page.locator('[data-wt="ra-feed"]');

  // Current feed rows, straight from the DOM (type + country per row).
  const feedState = (): Promise<Row[]> => page.evaluate(() => {
    const txt = (el: Element) => (el.textContent || '').trim();
    const f = document.querySelector('[data-wt="ra-feed"]');
    const list = f && f.querySelector('.overflow-y-auto');
    if (!list) return [] as Row[];
    return [...list.children].map((r) => {
      const spans = [...r.querySelectorAll('span')];
      const type = spans[0] ? txt(spans[0]) : '';
      const country = spans.map(txt).find((t) => /^[A-Z]{2}$/.test(t)) || '';
      return { type, country };
    });
  });

  // Text of every pill in the filter bar.
  const barPills = (): Promise<string[]> => page.evaluate(() => {
    const txt = (el: Element) => (el.textContent || '').trim();
    const f = document.querySelector('[data-wt="ra-feed"]');
    const bar = f && f.querySelector('.flex-wrap');
    return bar ? [...bar.querySelectorAll('button')].map(txt) : [];
  });

  // ONE wait for the live feed to be ready (mounted AND has rows). Collapsing the
  // old two sequential visibility waits into a single poll stops a slow feed-load
  // from cascading two budgets back-to-back under batch contention.
  let seed: Row = { type: '', country: '' };
  await expect
    .poll(async () => {
      const s = await feedState();
      if (s.length) seed = s[0];
      return s.length;
    }, { timeout: 60000, message: 'live feed should load at least one row' })
    .toBeGreaterThan(0);

  // ---- 1) EVENT TYPE filter (a type pill always exists) ------------------------
  const TYPE = seed.type;
  expect(TYPE).toMatch(/^[a-z_]+$/);

  await feed.getByRole('button', { name: TYPE, exact: true }).click();
  await expect
    .poll(async () => {
      const s = await feedState();
      return s.length >= 1 && s.every((r) => r.type === TYPE);
    }, { timeout: 15000, message: `every feed row should be ${TYPE}` })
    .toBe(true);

  // Reset — the feed returns to a populated, unfiltered state.
  await feed.getByRole('button', { name: 'All', exact: true }).click();
  await expect
    .poll(async () => (await feedState()).length, { timeout: 15000, message: 'feed should repopulate after reset' })
    .toBeGreaterThan(0);

  // ---- 2) COUNTRY filter (pills are conditional on multi-country traffic) ------
  const countryPills = (await barPills()).filter((p) => /^[A-Z]{2}$/.test(p));

  if (countryPills.length > 0) {
    // Multi-country window: the country pill must narrow the feed to that country.
    const COUNTRY = countryPills[0];
    await feed.getByRole('button', { name: COUNTRY, exact: true }).click();
    await expect
      .poll(async () => {
        const s = await feedState();
        return s.length >= 1 && s.every((r) => r.country === COUNTRY);
      }, { timeout: 15000, message: `every feed row should be ${COUNTRY}` })
      .toBe(true);
  } else {
    // Single-country window: the country control is correctly absent, and the feed
    // must then be internally consistent — every visible row shares one country.
    const s = await feedState();
    const countries = new Set(s.map((r) => r.country).filter(Boolean));
    expect(countries.size).toBeLessThanOrEqual(1);
  }
});
