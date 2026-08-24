# TC-P3 — Parts 34–50 Test Cases

Source: Testing_Complete_Guide.md (Parts 34–50)
Total: 150 test cases

---

### TC-P3-001
**Category:** Bug-Regression
**Test Name:** 3D tilt visible on SkillCard (Framer Motion outer / inner div separation)
**Steps:**
1. Navigate to the portfolio homepage (ml-portfolio Vercel URL)
2. Scroll to the Skills section
3. Hover over any skill card and move the mouse across it
**Expected Result:** The card tilts in 3D perspective tracking the mouse; the entrance animation is unaffected (card does not snap or flicker)
**Automation Hint:** `page.locator('.skill-card').hover()` then assert `transform` style contains `perspective` via `evaluate`
**Source:** Part34

---

### TC-P3-002
**Category:** Bug-Regression
**Test Name:** 3D tilt visible on NewsCard (Framer Motion separation)
**Steps:**
1. Navigate to the portfolio homepage
2. Scroll to the News section
3. Hover over any news card
**Expected Result:** News card shows 3D tilt; glow is visible (not too faint); card does not freeze or override entrance animation
**Automation Hint:** `page.locator('.news-card')` — assert `box-shadow` is non-empty on hover
**Source:** Part34

---

### TC-P3-003
**Category:** Bug-Regression
**Test Name:** Particle grid visible through all sections (no gelling)
**Steps:**
1. Navigate to the portfolio homepage
2. Scroll through every section (Hero, About, Skills, Projects, Pipeline, Timeline, News, Contact, Footer)
**Expected Result:** The particle canvas is visible through all sections — no section appears with a solid opaque background that hides the particles
**Automation Hint:** For each `section` element assert computed `background-color` is NOT fully opaque (alpha < 1); `page.evaluate(() => getComputedStyle(document.querySelector('section')).background)`
**Source:** Part34

---

### TC-P3-004
**Category:** Bug-Regression
**Test Name:** ParticleGrid mouse coordinates use clientX/Y only (no scrollY offset)
**Steps:**
1. Navigate to portfolio homepage
2. Scroll down 400px
3. Move mouse over particle canvas area
**Expected Result:** Particle repulsion follows the actual mouse cursor position on screen, not an offset position above it
**Automation Hint:** Visual regression screenshot comparison; `page.mouse.move(500, 300)` at scroll position 400
**Source:** Part34

---

### TC-P3-005
**Category:** Bug-Regression
**Test Name:** EDA Explorer hidden from sidebar in `?mode=ml`
**Steps:**
1. Open ML Unified at `/?mode=ml`
2. Inspect the sidebar
**Expected Result:** EDA Explorer item is NOT present in the sidebar
**Automation Hint:** `await expect(page.locator('#sidebar')).not.toContainText('EDA Explorer')` at URL `?mode=ml`
**Source:** Part34

---

### TC-P3-006
**Category:** Bug-Regression
**Test Name:** EDA Explorer hidden from sidebar in `?mode=vision`
**Steps:**
1. Open ML Unified at `/?mode=vision`
2. Inspect the sidebar
**Expected Result:** EDA Explorer item is NOT present in the sidebar
**Automation Hint:** `await expect(page.locator('#sidebar')).not.toContainText('EDA Explorer')` at URL `?mode=vision`
**Source:** Part34

---

### TC-P3-007
**Category:** Feature
**Test Name:** EDA Explorer visible in sidebar in `?mode=eda`
**Steps:**
1. Open ML Unified at `/?mode=eda`
2. Inspect the sidebar
**Expected Result:** EDA Explorer item IS present in the sidebar
**Automation Hint:** `await expect(page.locator('#sidebar')).toContainText('EDA Explorer')`
**Source:** Part34

---

### TC-P3-008
**Category:** Feature
**Test Name:** NeuralNetwork3D renders in Hero section
**Steps:**
1. Navigate to portfolio homepage
2. Inspect the Hero section
**Expected Result:** A Three.js canvas element is present and visible in the hero area (not blank/error); particles/nodes visible
**Automation Hint:** `page.locator('canvas').first()` — assert `isVisible()` returns true; no console errors
**Source:** Part34

---

### TC-P3-009
**Category:** Feature
**Test Name:** DataCube3D renders in About section with 6 faces
**Steps:**
1. Navigate to portfolio homepage
2. Scroll to the About section
3. Locate the DataCube element
**Expected Result:** A 3D cube is visible; faces show labels: "96.7% Accuracy", "4+ Live Apps", "2+ Years ML", "3.7/4 GPA", "CNN", "RAG"
**Automation Hint:** `page.locator('[class*="cube"]')` — assert contains text "96.7%"
**Source:** Part34

---

### TC-P3-010
**Category:** Feature
**Test Name:** MagneticButton CTA drifts toward cursor
**Steps:**
1. Navigate to portfolio homepage Hero section
2. Hover over a CTA button
**Expected Result:** The button element drifts slightly toward the cursor position; springs back on mouse leave
**Automation Hint:** `page.mouse.move(cx, cy)` over button, assert `transform` style changes, then move away and assert it resets
**Source:** Part34

---

### TC-P3-011
**Category:** UI
**Test Name:** Glassmorphism applied to ProjectCard, SkillCard, NewsCard
**Steps:**
1. Navigate to portfolio homepage
2. Inspect computed styles on a project card, a skill card, and a news card
**Expected Result:** Each card has `backdrop-filter: blur(14px)` and `background` uses the `--bg-glass` variable (semi-transparent)
**Automation Hint:** `page.evaluate(() => getComputedStyle(document.querySelector('[class*="project-card"]')).backdropFilter)` — assert contains `blur`
**Source:** Part34

---

### TC-P3-012
**Category:** Feature
**Test Name:** Portfolio favicon is neural network SVG (not default Vercel icon)
**Steps:**
1. Navigate to portfolio homepage
2. Check the favicon in the browser tab
**Expected Result:** The favicon is a neural network node pattern SVG (indigo/sky/emerald gradient square), not the default Vercel triangle or browser globe
**Automation Hint:** `page.evaluate(() => document.querySelector('link[rel="icon"]').href)` — assert it contains `.svg` and does NOT contain `vercel`
**Source:** Part34

---

### TC-P3-013
**Category:** UI
**Test Name:** No public email address on Contact page
**Steps:**
1. Navigate to portfolio homepage
2. Search the DOM text content of Contact, About, and Footer sections
**Expected Result:** The string "ramleo84@gmail.com" does NOT appear anywhere on the page
**Automation Hint:** `const body = await page.textContent('body'); expect(body).not.toContain('ramleo84@gmail.com')`
**Source:** Part34

---

### TC-P3-014
**Category:** Feature
**Test Name:** ML Unified gradient top bar present
**Steps:**
1. Open ML Unified at `/?mode=ml`
2. Inspect the very top of the page
**Expected Result:** A 3px gradient bar (indigo→sky→emerald) is visible at the top of the page
**Automation Hint:** `page.locator('.gradient-top-bar')` — assert `isVisible()` and computed `height` is ~3px
**Source:** Part35

---

### TC-P3-015
**Category:** Feature
**Test Name:** ML Unified nav title renders as gradient text
**Steps:**
1. Open ML Unified
2. Inspect the navigation title
**Expected Result:** The navigation title has gradient text styling (background-clip text pattern)
**Automation Hint:** `page.locator('.gradient-text')` — assert `background-image` computed style contains `gradient`
**Source:** Part35

---

### TC-P3-016
**Category:** Feature
**Test Name:** ML Unified sidebar active item shows glassmorphism + accent bar
**Steps:**
1. Open ML Unified at `/?mode=ml`
2. Click any model in the sidebar
**Expected Result:** The active sidebar item shows: glassmorphism background, a colored left accent bar, and a glowing dot; inactive items have no accent bar
**Automation Hint:** `page.locator('.sidebar-item.active')` — assert `border-left` or `border-left-color` is non-transparent; `backdrop-filter` is present
**Source:** Part35

---

### TC-P3-017
**Category:** Feature
**Test Name:** `--active-accent` CSS variable changes per selected model
**Steps:**
1. Open ML Unified
2. Select the Diabetes model (green accent expected)
3. Record `--active-accent` value
4. Select the Titanic model (sky blue accent expected)
5. Record `--active-accent` value
**Expected Result:** `--active-accent` is different between models and matches the documented accent color for each model
**Automation Hint:** `page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--active-accent'))`
**Source:** Part35

---

### TC-P3-018
**Category:** Bug-Regression
**Test Name:** ML Unified nav title selector uses ID not class (no conflict with gradient-text)
**Steps:**
1. Open ML Unified
2. Switch between modes (`?mode=ml`, `?mode=eda`)
3. Observe the nav title text
**Expected Result:** Nav title updates correctly in each mode (e.g., "ML Unified" vs "EDA Explorer") without any rendering conflict
**Automation Hint:** Navigate to `?mode=eda`, `await expect(page.locator('#nav-title-el')).toContainText('EDA')`
**Source:** Part35

---

### TC-P3-019
**Category:** Bug-Regression
**Test Name:** ML Unified favicon is embedded data URI (no HTTP request, no stale cache)
**Steps:**
1. Open ML Unified in an incognito/private window
2. Check the browser tab favicon immediately after page load
**Expected Result:** The neural network SVG favicon is visible immediately; the old triangle/default icon does not appear
**Automation Hint:** `page.evaluate(() => document.querySelector('link[rel="icon"]').href)` — assert starts with `data:image/svg+xml;base64,`
**Source:** Part36

---

### TC-P3-020
**Category:** Feature
**Test Name:** Sidebar items stagger-animate on page load
**Steps:**
1. Open ML Unified (hard reload)
2. Observe the sidebar items
**Expected Result:** Sidebar items fade in sequentially with a ~55ms stagger between each item, sliding in from below; not all visible instantly at once
**Automation Hint:** Record timestamps of when each `.sb-anim` becomes visible using `page.evaluate`; verify stagger intervals > 40ms
**Source:** Part36

---

### TC-P3-021
**Category:** Feature
**Test Name:** Active sidebar dot pulses on model selection
**Steps:**
1. Open ML Unified
2. Click a model in the sidebar
**Expected Result:** The colored dot next to the selected model briefly scales up (to ~2.2×) and back — a pulse animation — after selection
**Automation Hint:** `page.locator('.dot-pulse')` — assert class is present on the active dot immediately after click
**Source:** Part36

---

### TC-P3-022
**Category:** Feature
**Test Name:** Main panel slides in from below on model selection
**Steps:**
1. Open ML Unified
2. Click any model
**Expected Result:** The main content panel animates sliding in from below (36px) over ~380ms; previous content fades/slides out first
**Automation Hint:** Listen for CSS transition on `#main`; verify `animateMainIn` runs (check class or transform style transitions)
**Source:** Part36

---

### TC-P3-023
**Category:** Feature
**Test Name:** Predict button shows shimmer animation while prediction is loading
**Steps:**
1. Open ML Unified, select a model
2. Fill in sample values
3. Click Predict
4. Observe the Predict button during the API call
**Expected Result:** The Predict button shows a shimmer/loading animation (`.btn-shimmer` class) while the prediction is in progress
**Automation Hint:** `page.locator('.btn-shimmer')` — assert visible between click and result appearing
**Source:** Part36

---

### TC-P3-024
**Category:** Feature
**Test Name:** Predict button shows green success flash after prediction
**Steps:**
1. Open ML Unified, select a model
2. Fill in sample values, click Predict
3. Wait for result
4. Observe the Predict button
**Expected Result:** After result appears, the Predict button briefly flashes green (`.btn-success-flash` class, ~900ms) then returns to normal
**Automation Hint:** `page.locator('.btn-success-flash')` — assert class present then removed within ~1s of result
**Source:** Part36

---

### TC-P3-025
**Category:** Feature
**Test Name:** Result card slides up from below after prediction
**Steps:**
1. Open ML Unified, select a model
2. Fill in sample values, click Predict
**Expected Result:** The result card animates sliding up from below when the prediction result appears; `.result-reveal` class triggers this
**Automation Hint:** `page.locator('.result-reveal')` — assert visible and then check transition animation applied
**Source:** Part36

---

### TC-P3-026
**Category:** Feature
**Test Name:** Probability bars animate from 0 to value after classification
**Steps:**
1. Open ML Unified, select a classification model (e.g., Iris)
2. Click Fill Sample, then Predict
3. Observe the confidence bars in the result
**Expected Result:** Probability bars start at 0 width and animate to their final percentage values; bars do NOT appear at full width instantly
**Automation Hint:** Immediately after predict completes, measure bar width; repeat 80ms later — first reading should be smaller
**Source:** Part36

---

### TC-P3-027
**Category:** Feature
**Test Name:** Regression result value counts up (count-up animation)
**Steps:**
1. Open ML Unified, select Insurance Premium Estimator
2. Click Fill Sample, then Predict
**Expected Result:** The predicted regression value (e.g., a dollar amount) counts up from 0 to the final value rather than appearing immediately
**Automation Hint:** Check `#regVal` element text immediately after result; value should start near 0 then increase
**Source:** Part36

---

### TC-P3-028
**Category:** Feature
**Test Name:** Metric pill shows count-up animation on model selection
**Steps:**
1. Open ML Unified
2. Click any model in the sidebar
3. Observe the accuracy/metric pill in the model header
**Expected Result:** The metric value (e.g., "77.5%") counts up from 0 to the final value over ~600ms
**Automation Hint:** `page.locator('.metric-val')` — text right after click should be near "0", text 700ms later should be final value
**Source:** Part36

---

### TC-P3-029
**Category:** Feature
**Test Name:** Particle canvas is present and fixed behind all content
**Steps:**
1. Open ML Unified
2. Inspect DOM structure
**Expected Result:** A `<canvas>` element with id `bg-canvas` is present, `position: fixed`, `z-index: 0`, sized to viewport
**Automation Hint:** `page.locator('#bg-canvas')` — assert `isVisible()`, computed `position === 'fixed'`
**Source:** Part36

---

### TC-P3-030
**Category:** Feature
**Test Name:** ML Unified Geist font applied globally
**Steps:**
1. Open ML Unified
2. Check the computed font-family on the body element
**Expected Result:** `font-family` includes `Geist` as the first non-system font
**Automation Hint:** `page.evaluate(() => getComputedStyle(document.body).fontFamily)` — assert contains `Geist`
**Source:** Part36

---

### TC-P3-031
**Category:** Feature
**Test Name:** ML Unified neural network logo mark SVG is present in nav
**Steps:**
1. Open ML Unified
2. Inspect the navigation logo area
**Expected Result:** The `.nav-logo-mark` contains an inline SVG (neural network glyph), not plain "ML" text
**Automation Hint:** `page.locator('.nav-logo-mark svg')` — assert count >= 1
**Source:** Part36

---

### TC-P3-032
**Category:** Feature
**Test Name:** No emoji characters used in ML Unified UI (SVG replacements only)
**Steps:**
1. Open ML Unified
2. Navigate through all sections: ML models, EDA, Vision, Clustering
3. Inspect visible text and icons
**Expected Result:** No emoji characters (Unicode emoji range U+1F300-U+1FAFF) visible; all icons are SVG elements
**Automation Hint:** `const text = await page.textContent('body'); expect(text).not.toMatch(/[\u{1F300}-\u{1FAFF}]/u)`
**Source:** Part36

---

### TC-P3-033
**Category:** Feature
**Test Name:** Live Metrics panel has glassmorphism + gradient top bar
**Steps:**
1. Open ML Unified
2. Open the Live Metrics panel (click the metrics button)
**Expected Result:** The Live Metrics panel has a glassmorphism background (blur), a 3px gradient top bar, and colored stat boxes (green for Uptime/0% Errors)
**Automation Hint:** `page.locator('[class*="live-metrics"]')` — assert `backdrop-filter` computed style contains `blur`
**Source:** Part36

---

### TC-P3-034
**Category:** Bug-Regression
**Test Name:** EDA Explorer HTML export footer link opens EDA mode (not default ML mode)
**Steps:**
1. Open ML Unified in EDA mode
2. Upload a CSV and run analysis
3. Click Export / Download report
4. Open the downloaded HTML file
5. Click the footer link to the ML Unified app
**Expected Result:** The footer link URL is `ml-unified.onrender.com/?mode=eda` — clicking it opens EDA mode, not the default ML model view
**Automation Hint:** Parse the exported HTML file; `expect(html).toContain('?mode=eda')` in the footer anchor `href`
**Source:** Part37

---

### TC-P3-035
**Category:** Bug-Regression
**Test Name:** EDA Explorer HTML export contains favicon (works offline)
**Steps:**
1. Export an EDA report from ML Unified
2. Open the downloaded HTML file offline (no network)
3. Check the browser tab
**Expected Result:** The neural network favicon is visible in the browser tab without any network request (base64 data URI embedded in `<head>`)
**Automation Hint:** Parse exported HTML; `expect(html).toMatch(/<link rel="icon" href="data:image\/svg\+xml;base64,/)`
**Source:** Part37

---

### TC-P3-036
**Category:** Feature
**Test Name:** Theme-aware HTML export — light theme uses light CSS
**Steps:**
1. Open ML Unified and switch to light theme
2. Upload a CSV and run EDA
3. Click Export report
4. Open the downloaded HTML
**Expected Result:** The exported HTML has a light-mode CSS block: white/light background (`#f0f4f8`), dark text, proper contrast
**Automation Hint:** Export HTML; parse CSS; assert body `background` includes `#f0f4f8` or similar light value
**Source:** Part37

---

### TC-P3-037
**Category:** Feature
**Test Name:** Theme-aware HTML export — dark theme uses dark CSS
**Steps:**
1. Open ML Unified in dark theme (default)
2. Export an EDA report
3. Open the downloaded HTML
**Expected Result:** Exported HTML has dark-mode CSS: dark background, light text (unchanged dark export CSS)
**Automation Hint:** Export HTML; parse CSS; assert body `background` is dark (starts with `#0` or similar)
**Source:** Part37

---

### TC-P3-038
**Category:** Feature
**Test Name:** Hero NeuralNetwork3D responds to mouse parallax
**Steps:**
1. Navigate to portfolio homepage
2. Move the mouse from the left edge to the right edge of the Hero section
**Expected Result:** The neural network sphere rotates/shifts slightly in response to horizontal mouse movement — not just auto-rotating independently
**Automation Hint:** `page.mouse.move(100, 300)` — capture `<canvas>` pixel sample; `page.mouse.move(1400, 300)` — capture again; assert images differ
**Source:** Part37

---

### TC-P3-039
**Category:** Animation
**Test Name:** NeuralNetwork3D uses darker line color in light theme
**Steps:**
1. Open portfolio, switch to light theme
2. Inspect the 3D neural network canvas in the Hero section
**Expected Result:** Network lines are rendered darker (more contrast) in light mode than in dark mode
**Automation Hint:** Visual regression test comparing canvas rendering in dark vs light mode
**Source:** Part37

---

### TC-P3-040
**Category:** Feature
**Test Name:** Pipeline SVG icons are rendered as SVG tiles (no emojis)
**Steps:**
1. Navigate to portfolio homepage, scroll to Pipeline section
2. Inspect each of the 7 pipeline stage cards
**Expected Result:** Each stage card shows a tinted SVG tile icon (not an emoji character) for: Data Ingestion, Exploratory Analysis, Feature Engineering, Model Training, Evaluation, Deployment, Monitoring
**Automation Hint:** `page.locator('[class*="pipeline"] svg')` — assert count >= 7
**Source:** Part37

---

### TC-P3-041
**Category:** Animation
**Test Name:** `useIsDark` hook drives light theme blob opacity correctly
**Steps:**
1. Open portfolio in dark mode — observe Hero blobs
2. Switch to light mode
3. Observe Hero blobs
**Expected Result:** Blobs are more opaque in light mode (blob 1: 0.22, blob 2: 0.18, blob 3: 0.14 vs dark values); blobs remain visible in both modes
**Automation Hint:** Visual regression comparing blob opacity at dark vs light theme
**Source:** Part37

---

### TC-P3-042
**Category:** Feature
**Test Name:** Hamburger menu visible on mobile (768px), nav links hidden
**Steps:**
1. Set viewport to 375x812
2. Navigate to portfolio homepage
**Expected Result:** Navigation links (About, Skills, Projects, etc.) are hidden; a hamburger button is visible and tappable
**Automation Hint:** `await page.setViewportSize({width: 375, height: 812})` — `expect(page.locator('.nav-hamburger')).toBeVisible()`, `expect(page.locator('.nav-links')).toBeHidden()`
**Source:** Part38

---

### TC-P3-043
**Category:** Bug-Regression
**Test Name:** Theme toggle always visible on mobile (not hidden with nav links)
**Steps:**
1. Set viewport to 375x812
2. Navigate to portfolio homepage
**Expected Result:** The theme toggle (dark/light switch) is always visible on mobile even when nav links are hidden
**Automation Hint:** `page.setViewportSize({width: 375, height: 812})` — `expect(page.locator('[data-testid="theme-toggle"]')).toBeVisible()`
**Source:** Part38

---

### TC-P3-044
**Category:** Feature
**Test Name:** Hamburger menu opens dropdown with all nav links + Resume
**Steps:**
1. Set viewport to 375x812
2. Navigate to portfolio homepage
3. Click the hamburger button
**Expected Result:** A dropdown appears showing all navigation links (About, Skills, Projects, Pipeline, Timeline, Contact) plus a Resume link
**Automation Hint:** `page.locator('.nav-hamburger').click()` — then assert all nav links visible in the mobile dropdown
**Source:** Part38

---

### TC-P3-045
**Category:** Feature
**Test Name:** Timeline shows single-column layout on mobile
**Steps:**
1. Set viewport to 375x812
2. Scroll to the Experience/Timeline section
**Expected Result:** Timeline renders as a single column (not two alternating columns); the vertical line is at the left rail (`left: 0.5rem`), cards are full width
**Automation Hint:** `page.setViewportSize({width: 375, height: 812})` — `page.locator('.timeline-line')` — assert `left` style is `0.5rem`
**Source:** Part38

---

### TC-P3-046
**Category:** Bug-Regression
**Test Name:** Skills grid does not overflow on 320px viewport
**Steps:**
1. Set viewport to 320x568
2. Navigate to portfolio homepage
3. Scroll to Skills section
**Expected Result:** Skill cards do not overflow horizontally; grid is contained within viewport width
**Automation Hint:** `page.setViewportSize({width: 320, height: 568})` — assert no horizontal scrollbar, no element extends beyond `document.body.clientWidth`
**Source:** Part38

---

### TC-P3-047
**Category:** Bug-Regression
**Test Name:** Projects grid does not overflow on 320px viewport
**Steps:**
1. Set viewport to 320x568
2. Navigate to portfolio homepage
3. Scroll to Projects section
**Expected Result:** Project cards do not overflow horizontally; grid is contained within 320px
**Automation Hint:** Same as TC-P3-046 but assert on the Projects section cards
**Source:** Part38

---

### TC-P3-048
**Category:** Bug-Regression
**Test Name:** Pipeline stage cards have equal height (all cards in a row match tallest)
**Steps:**
1. Navigate to portfolio homepage
2. Scroll to the Pipeline section
3. Observe card heights within each row
**Expected Result:** All pipeline stage cards in the same row have equal height, including "Exploratory Analysis" (2-line title) which previously caused unequal heights
**Automation Hint:** `page.locator('[class*="stage-card"]').evaluateAll(els => els.map(e => e.offsetHeight))` — assert all values in a row are equal
**Source:** Part38

---

### TC-P3-049
**Category:** Feature
**Test Name:** Pipeline stage cards have glassmorphism + 3D tilt + accent bar
**Steps:**
1. Navigate to portfolio homepage, scroll to Pipeline section
2. Hover over a pipeline stage card
**Expected Result:** Card shows 3D tilt tracking mouse, shimmer overlay, 3px top accent bar, and a glassmorphism background
**Automation Hint:** `page.locator('[class*="stage-card"]').first().hover()` — assert `transform` style contains `perspective`, `backdrop-filter` contains `blur`
**Source:** Part38

---

### TC-P3-050
**Category:** Feature
**Test Name:** SVG icons used in Skills section (no emojis)
**Steps:**
1. Navigate to portfolio homepage, scroll to Skills section
2. Inspect each category icon (ML, DL, GenAI, NLP, CV, MLOps)
**Expected Result:** Each category shows an SVG icon (stroke-based neural network, lightning bolt, sparkle, chat bubble, eye, gear) — no emoji characters
**Automation Hint:** `page.locator('[class*="skill-category"] svg')` — assert count >= 6
**Source:** Part38

---

### TC-P3-051
**Category:** Feature
**Test Name:** SVG icons used in About/Contact/Footer (DockerHub, Location, GitHub, LinkedIn)
**Steps:**
1. Navigate to portfolio homepage
2. Check About, Contact, and Footer sections for social/location links
**Expected Result:** DockerHub shows Docker container grid SVG, Location shows map pin SVG, GitHub shows Octocat SVG, LinkedIn shows LinkedIn SVG — no emojis
**Automation Hint:** `page.locator('footer svg')` + `page.locator('[class*="about"] svg')` — assert relevant SVGs exist
**Source:** Part38

---

### TC-P3-052
**Category:** Feature
**Test Name:** Contact form success state uses CheckCircle SVG (not checkmark emoji)
**Steps:**
1. Navigate to portfolio homepage, scroll to Contact section
2. Fill in the contact form and submit
**Expected Result:** Success state shows a circular checkmark SVG icon (36px), not the checkmark emoji
**Automation Hint:** After form submit, `page.locator('[class*="contact"] svg circle')` — assert visible; assert no emoji in textContent
**Source:** Part38

---

### TC-P3-053
**Category:** Bug-Regression
**Test Name:** ruff check passes on ml-vision tests (no E401 double import)
**Steps:**
1. In ML-Unified repo, run: `.venv/bin/ruff check services/ml-vision/tests/conftest.py`
**Expected Result:** Zero ruff errors; in particular no E401 "multiple imports on one line" error
**Automation Hint:** `subprocess.run(['.venv/bin/ruff', 'check', 'services/ml-vision/tests/conftest.py'])` — assert returncode == 0
**Source:** Part39

---

### TC-P3-054
**Category:** Backend API
**Test Name:** All 61 ML Unified backend tests pass
**Steps:**
1. In ML-Unified repo, run: `pytest services/ml-api/tests/ services/ml-eda/tests/ -v`
**Expected Result:** 61 tests collected, 61 passed, 0 failed, 0 errors
**Automation Hint:** `subprocess.run(['pytest', 'services/ml-api/tests/', 'services/ml-eda/tests/', '-v'])` — assert 61 passed
**Source:** Part39

---

### TC-P3-055
**Category:** Feature
**Test Name:** Chatbot widget is present and opens on click (portfolio)
**Steps:**
1. Navigate to portfolio homepage
2. Locate the chatbot trigger button (bottom-right floating button)
3. Click it
**Expected Result:** The chatbot panel opens, showing message history area, input field, and send button; the UI has a glass card appearance with accent bar
**Automation Hint:** `page.locator('[class*="chatbot"]').click()` — then `expect(page.locator('[class*="chat-input"]')).toBeVisible()`
**Source:** Part39

---

### TC-P3-056
**Category:** Feature
**Test Name:** Chatbot shows provider selector (Gemini, Claude, Groq)
**Steps:**
1. Open the chatbot widget on portfolio homepage
2. Look for provider selection controls in the header
**Expected Result:** Three provider pills (Gemini, Claude, Groq) are visible and one is active
**Automation Hint:** `page.locator('[class*="provider-pill"]')` — assert count === 3
**Source:** Part39

---

### TC-P3-057
**Category:** E2E
**Test Name:** Chatbot responds to a message via Gemini provider
**Steps:**
1. Open the chatbot widget
2. Ensure Gemini provider is selected
3. Type "What models do you have?" and press Enter
**Expected Result:** A response appears in the chat within ~10 seconds (no 404 or "model not found" error); typing indicator appears during loading
**Automation Hint:** `page.locator('[class*="chat-input"]').fill('What models do you have?'); page.keyboard.press('Enter')` — wait for response bubble; timeout 15000
**Source:** Part39

---

### TC-P3-058
**Category:** Bug-Regression
**Test Name:** Gemini API uses correct model gemini-2.5-flash (not 1.5-flash which 404s)
**Steps:**
1. Open the portfolio chatbot
2. Send any message with Gemini provider selected
3. Check server logs / network response
**Expected Result:** Chat response is received successfully (HTTP 200 from `/api/chat`); no "model not found" error
**Automation Hint:** `page.route('/api/chat', route => { /* intercept */ })` — assert no 404 or model-not-found in response body
**Source:** Part39

---

### TC-P3-059
**Category:** Bug-Regression
**Test Name:** Glass cards visible in light mode — Portfolio Skills and Pipeline
**Steps:**
1. Open portfolio, switch to light theme
2. Scroll to Skills section — inspect skill cards
3. Scroll to Pipeline section — inspect pipeline stage cards
**Expected Result:** Cards are visible with a white/light background (`#ffffff`), visible border (`rgba(0,0,0,0.10)`), and subtle shadow — NOT invisible white-on-white
**Automation Hint:** `page.locator('[class*="skill-card"]').first()` — assert `background-color` is not transparent and not the same as page background
**Source:** Part39

---

### TC-P3-060
**Category:** Feature
**Test Name:** Theme palette picker opens dropdown with 4 options
**Steps:**
1. Navigate to portfolio homepage
2. Click the palette picker button in the navbar (gradient circle)
**Expected Result:** A dropdown appears showing 4 palette options: Cosmic, Sunset, Aurora, Ocean — each with a color swatch and label
**Automation Hint:** `page.locator('[class*="palette-btn"]').click()` — assert 4 dropdown items visible
**Source:** Part39

---

### TC-P3-061
**Category:** Feature
**Test Name:** Selecting Sunset palette changes accent colors site-wide
**Steps:**
1. Navigate to portfolio homepage
2. Open palette picker, select Sunset
3. Observe the navbar Resume button, Hero CTA, and footer bar
**Expected Result:** Gradient elements shift to orange/amber/yellow (`--accent-from: #f97316`) throughout the site
**Automation Hint:** After click, `page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent-from'))` — assert `#f97316`
**Source:** Part39

---

### TC-P3-062
**Category:** Feature
**Test Name:** Palette selection persists across page reload (localStorage)
**Steps:**
1. Navigate to portfolio homepage
2. Select the Aurora palette
3. Reload the page
**Expected Result:** Aurora palette is still active after reload (purple/pink/rose gradient visible); no flash of default palette before restoration
**Automation Hint:** After palette select + reload, `page.evaluate(() => localStorage.getItem('palette'))` — assert `'aurora'`; assert `--accent-from` value matches aurora colors
**Source:** Part39

---

### TC-P3-063
**Category:** Bug-Regression
**Test Name:** Palette picker dropdown closes when clicking outside
**Steps:**
1. Open the palette picker dropdown in the portfolio navbar
2. Click anywhere on the page body (outside the dropdown)
**Expected Result:** The dropdown closes; no orphaned overlay element blocks interaction
**Automation Hint:** `page.locator('[class*="palette-btn"]').click()` to open; `page.locator('main').click()` to close; assert dropdown not visible
**Source:** Part39

---

### TC-P3-064
**Category:** Feature
**Test Name:** Portfolio "Launch App" passes `?palette=xxx` URL parameter
**Steps:**
1. Navigate to portfolio homepage
2. Select the Ocean palette
3. Click "Launch App" on any project card (e.g., ML Unified)
**Expected Result:** The launched URL includes `?palette=ocean` (or `&palette=ocean`)
**Automation Hint:** `page.on('popup', popup => { expect(popup.url()).toContain('palette=ocean') })` before clicking Launch
**Source:** Part40

---

### TC-P3-065
**Category:** Feature
**Test Name:** ML Unified reads `?palette=` from URL and applies it
**Steps:**
1. Open ML Unified at `/?palette=sunset`
2. Observe gradient top bar, logo mark, and Predict button
**Expected Result:** Brand elements use orange/amber/yellow gradient (Sunset palette), not default indigo/sky/emerald
**Automation Hint:** `page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent-from'))` — assert contains orange value
**Source:** Part40

---

### TC-P3-066
**Category:** Feature
**Test Name:** ML Unified cleans `?palette=` from URL after applying
**Steps:**
1. Open ML Unified at `/?palette=sunset`
2. Wait for page to fully load
3. Check the browser URL bar
**Expected Result:** The `?palette=` parameter is no longer in the URL; the palette is still applied (localStorage persists it)
**Automation Hint:** `await page.waitForURL(url => !url.includes('palette='))` or check `page.url()` does not contain `palette=`
**Source:** Part40

---

### TC-P3-067
**Category:** Feature
**Test Name:** ML Unified per-model dots retain their identity colors regardless of palette
**Steps:**
1. Open ML Unified with `?palette=sunset`
2. Observe sidebar model dots
**Expected Result:** Sidebar model dots still show their individual accent colors (green for Diabetes, sky for Titanic, etc.) — NOT the sunset orange
**Automation Hint:** `page.locator('.model-dot')` for each model — assert green dot is green, not orange
**Source:** Part40

---

### TC-P3-068
**Category:** Backend API
**Test Name:** `GET /pipeline/{model_id}` returns correct schema structure
**Steps:**
1. Send `GET /pipeline/diabetes` to ml-api
**Expected Result:** Response is 200 JSON with keys: `model_id`, `title`, `task`, `input_fields`, `steps`; `steps` contains at least one preprocessor and one estimator
**Automation Hint:**
```python
def test_pipeline_diabetes(client):
    resp = client.get('/pipeline/diabetes')
    assert resp.status_code == 200
    data = resp.json()
    assert 'steps' in data
    kinds = [s['kind'] for s in data['steps']]
    assert 'preprocessor' in kinds
    assert 'estimator' in kinds
```
**Source:** Part41

---

### TC-P3-069
**Category:** Backend API
**Test Name:** `/pipeline/{model_id}` returns key hyperparameters for RandomForestClassifier
**Steps:**
1. Send `GET /pipeline/diabetes`
**Expected Result:** Estimator step includes `n_estimators` and `max_depth` in `params`
**Automation Hint:**
```python
def test_pipeline_rf_params(client):
    resp = client.get('/pipeline/diabetes')
    estimator = next(s for s in resp.json()['steps'] if s['kind'] == 'estimator')
    assert 'n_estimators' in estimator['params']
```
**Source:** Part41

---

### TC-P3-070
**Category:** Backend API
**Test Name:** `/pipeline/{model_id}` returns 404 for unknown model
**Steps:**
1. Send `GET /pipeline/nonexistent_model`
**Expected Result:** Response is HTTP 404 (not 500)
**Automation Hint:**
```python
def test_pipeline_unknown(client):
    resp = client.get('/pipeline/nonexistent_model')
    assert resp.status_code == 404
```
**Source:** Part41

---

### TC-P3-071
**Category:** Feature
**Test Name:** Pipeline tab present in ML Unified model header
**Steps:**
1. Open ML Unified, select any model
2. Inspect the tabs in the model header
**Expected Result:** "Predict" and "Pipeline" tabs are visible as underline-style nav tabs
**Automation Hint:** `page.locator('[class*="tab"]')` — assert text content includes "Pipeline"
**Source:** Part41

---

### TC-P3-072
**Category:** Feature
**Test Name:** Pipeline tab loads and shows flow diagram on first click
**Steps:**
1. Open ML Unified, select Diabetes model
2. Click the "Pipeline" tab
**Expected Result:** A flow diagram appears showing numbered steps: (1) Input with feature chips, (2) Preprocessing with column transformer details, (3) Estimator with hyperparameter pills
**Automation Hint:** `page.locator('[class*="pipeline-step"]')` — assert count >= 3 after tab click
**Source:** Part41

---

### TC-P3-073
**Category:** Feature
**Test Name:** Pipeline tab is lazy-loaded (no extra network request on tab toggle)
**Steps:**
1. Open ML Unified, select Diabetes model
2. Click Pipeline tab — observe network request (first load)
3. Click Predict tab, then click Pipeline tab again
**Expected Result:** On first click, a `GET /pipeline/diabetes` request is made; on second click, no repeat request (DOM cached)
**Automation Hint:** Track network requests via `page.on('request', ...)` — `GET /pipeline/diabetes` should appear exactly once
**Source:** Part41

---

### TC-P3-074
**Category:** Bug-Regression
**Test Name:** Light theme — model header uses `bg-card` not `bg-glass` (visible on light bg)
**Steps:**
1. Open ML Unified, switch to light theme
2. Select any model
3. Inspect the model header panel
**Expected Result:** Model header is clearly visible on the light background (white/off-white card with shadow), NOT semi-transparent glass that disappears on white
**Automation Hint:** In light theme, `page.locator('.model-header')` — assert background is NOT `rgba(255,255,255,0.6)` (the glass value)
**Source:** Part41

---

### TC-P3-075
**Category:** Bug-Regression
**Test Name:** Light theme — result card uses `bg-card` not `bg-glass` (visible)
**Steps:**
1. Open ML Unified in light theme
2. Run a prediction
3. Inspect the result card
**Expected Result:** Result card is clearly visible (white card with shadow), not invisible on the light background
**Automation Hint:** `page.locator('.result-state')` — assert opacity >= 0.9 and not fully transparent background
**Source:** Part41

---

### TC-P3-076
**Category:** Bug-Regression
**Test Name:** Light theme — SHAP panel uses `bg-card` not `bg-glass` (visible)
**Steps:**
1. Open ML Unified in light theme
2. Run a prediction, then view Feature Impact
3. Inspect the SHAP panel
**Expected Result:** SHAP panel is clearly visible on light background
**Automation Hint:** `page.locator('.shap-panel')` — assert background-color is not transparent
**Source:** Part41

---

### TC-P3-077
**Category:** Feature
**Test Name:** Model header shows editorial-style layout (no card-in-card nesting)
**Steps:**
1. Open ML Unified, select any model
**Expected Result:** Model title is large (2rem) and flows directly on the background — not trapped inside a white card floating on a grey background; tabs are underline style, not pill buttons
**Automation Hint:** `page.locator('.u-title')` — assert `font-size` >= 28px; assert no nested white card wrapping the title
**Source:** Part41

---

### TC-P3-078
**Category:** Feature
**Test Name:** Form field labels in Predict section are sentence case (not ALL-CAPS)
**Steps:**
1. Open ML Unified, select any model (e.g., Diabetes)
2. Inspect form field labels
**Expected Result:** Form labels are sentence case (e.g., "Glucose (mg/dL)") — NOT ALL CAPS with letter-spacing
**Automation Hint:** `page.locator('.form-label').first().textContent()` — assert result is not all uppercase
**Source:** Part41

---

### TC-P3-079
**Category:** Feature
**Test Name:** EDA tab navigation uses `color-mix` with `--active-accent` (not hardcoded #34d399)
**Steps:**
1. Open ML Unified in EDA mode with Sunset palette applied
2. Click different EDA sub-tabs (Overview, Distribution, Correlation, etc.)
**Expected Result:** Active tab indicator uses the orange/sunset palette accent color, NOT the hardcoded emerald green `#34d399`
**Automation Hint:** With sunset palette, check active EDA tab `border-bottom-color` — assert NOT `#34d399`
**Source:** Part41

---

### TC-P3-080
**Category:** Bug-Regression
**Test Name:** Insurance schema correctly labels model as "Random Forest" (not "Gradient Boosting")
**Steps:**
1. Open ML Unified, select the Insurance Premium Estimator model
2. Inspect the model type label in the header
**Expected Result:** Model type shows "Random Forest" — NOT "Gradient Boosting"
**Automation Hint:** `page.locator('.model-eyebrow')` — assert contains "Random Forest"
**Source:** Part42

---

### TC-P3-081
**Category:** Feature
**Test Name:** Confidence bar chart: predicted class has "Predicted" badge
**Steps:**
1. Open ML Unified, select Iris Species Classifier
2. Fill sample and click Predict
**Expected Result:** The top-confidence class bar shows a "Predicted" pill badge; non-predicted bars are at 66% opacity
**Automation Hint:** `page.locator('.predicted-badge')` — assert visible after prediction
**Source:** Part42

---

### TC-P3-082
**Category:** Animation
**Test Name:** Confidence bars animate in staggered (80ms per bar)
**Steps:**
1. Open ML Unified, select a classifier
2. Fill sample and Predict
3. Observe the confidence bars appearing
**Expected Result:** Bars animate in sequentially (staggered entrance), not all at once
**Automation Hint:** Check `animation-delay` or `transition-delay` CSS properties on bar elements — verify progressive values
**Source:** Part42

---

### TC-P3-083
**Category:** Feature
**Test Name:** What-if tab present in model header
**Steps:**
1. Open ML Unified, select any model
2. Check the tab bar
**Expected Result:** "What-if" tab is visible (alongside Predict and Pipeline)
**Automation Hint:** `page.locator('[class*="tab"]')` — assert text includes "What-if" (case-insensitive)
**Source:** Part42

---

### TC-P3-084
**Category:** Feature
**Test Name:** What-if analysis generates SVG line chart for numeric feature
**Steps:**
1. Open ML Unified, select Diabetes model
2. Click What-if tab
3. Select a numeric feature chip (e.g., Glucose)
**Expected Result:** An SVG line chart appears showing how predicted probability varies as Glucose changes across its range; chart has gradient fill and dashed sample marker
**Automation Hint:** `page.locator('[class*="whatif"] svg')` — assert visible with `path` elements
**Source:** Part42

---

### TC-P3-085
**Category:** Feature
**Test Name:** What-if analysis generates bar chart for categorical feature
**Steps:**
1. Open ML Unified, select Titanic Survival Predictor
2. Click What-if tab
3. Select a categorical feature chip (e.g., Sex)
**Expected Result:** Bar chart rendered showing survival probability for each category option (male, female)
**Automation Hint:** `page.locator('[class*="whatif"] svg rect')` — assert count matches number of categorical options
**Source:** Part42

---

### TC-P3-086
**Category:** Feature
**Test Name:** Side-by-side layout for Object Detection (Original | Detected)
**Steps:**
1. Open ML Unified in Vision mode (`?mode=vision`)
2. Click Object Detection
3. Upload an image and click Detect
**Expected Result:** Both the original image and the annotated/detected image are shown side by side
**Automation Hint:** `page.locator('.ip-before-after')` — assert two image elements inside it
**Source:** Part42

---

### TC-P3-087
**Category:** Feature
**Test Name:** Side-by-side layout for Image Segmentation (Original | Segmented)
**Steps:**
1. Open ML Unified in Vision mode
2. Click Image Segmentation
3. Upload an image and run segmentation
**Expected Result:** Both the original image and the segmented overlay are shown side by side
**Automation Hint:** `page.locator('.ip-before-after')` — assert two image elements inside it within segmentation panel
**Source:** Part42

---

### TC-P3-088
**Category:** Animation
**Test Name:** Ambient blobs change color when switching vision sections
**Steps:**
1. Open ML Unified in Vision mode
2. Click Image Classifier — observe blob colors
3. Click Image Processing — observe blob colors change
4. Click Object Detection — observe blob colors
5. Click Image Segmentation — observe blob colors
**Expected Result:** Blobs transition to different colors per section: Classifier=fuchsia, Processing=orange, Detection=sky blue, Segmentation=violet; transition takes ~1.5s
**Automation Hint:** After clicking each section, capture computed `background` of `.bg-blob-1` — assert different values per section
**Source:** Part42

---

### TC-P3-089
**Category:** Animation
**Test Name:** Ambient blobs change color when switching ML models
**Steps:**
1. Open ML Unified, select Diabetes (expect green blobs)
2. Select Titanic (expect sky blue blobs)
3. Select Iris (expect indigo blobs)
4. Select Insurance (expect amber blobs)
**Expected Result:** Blob background color changes to match each model's accent color
**Automation Hint:** Per model select, assert `.bg-blob-1` background transitions to expected color
**Source:** Part42

---

### TC-P3-090
**Category:** E2E
**Test Name:** Batch image classification — upload multiple images and classify all
**Steps:**
1. Open ML Unified Vision — Image Classifier
2. Upload 3 images using the upload zone
3. Click "Classify All"
**Expected Result:** A thumbnail grid appears with all 3 images; each card shows a "Ready" status initially; after classify all, each card updates with top prediction label, confidence %, and 2 runner-ups; a progress bar shows "N / 3 classified..."
**Automation Hint:** `page.locator('.batch-grid')` — assert visible; `page.locator('.batch-card--done')` — assert count === 3 after classify
**Source:** Part42

---

### TC-P3-091
**Category:** Feature
**Test Name:** Batch card border color reflects confidence level
**Steps:**
1. Run batch classification with varied images
2. Find a card with high confidence, one with low confidence
**Expected Result:** High-confidence cards have fuchsia border (`.batch-card--done`); low-confidence cards have amber border (`.batch-card--low`); error cards have red border (`.batch-card--error`)
**Automation Hint:** After classify, check `.batch-card--low` has `border-color` that matches amber
**Source:** Part42

---

### TC-P3-092
**Category:** Feature
**Test Name:** Clear button empties batch grid
**Steps:**
1. Upload 3 images in Vision classifier
2. Click the Clear button
**Expected Result:** The batch grid is cleared; the upload zone reappears
**Automation Hint:** `page.locator('.batch-card')` — assert count === 0 after clear click
**Source:** Part42

---

### TC-P3-093
**Category:** Feature
**Test Name:** Mobile bottom tab bar appears on ≤640px viewport
**Steps:**
1. Set viewport to 390x844 (mobile)
2. Open ML Unified
**Expected Result:** A fixed bottom navigation bar appears with 5 tabs: Models, Vision, Cluster, EDA, Tools; the sidebar is hidden
**Automation Hint:** `page.setViewportSize({width: 390, height: 844})` — `expect(page.locator('[class*="bottom-tab"]')).toBeVisible()`, `expect(page.locator('#sidebar')).toBeHidden()`
**Source:** Part43

---

### TC-P3-094
**Category:** Feature
**Test Name:** Models bottom tab shows model chip strip
**Steps:**
1. On mobile viewport, tap the Models tab
**Expected Result:** A chip strip appears below the nav showing: Diabetes, Titanic, Iris, Insurance chips; tapping a chip selects that model
**Automation Hint:** `page.locator('[class*="mobile-strip"] [class*="chip"]')` — assert >= 4 chips visible after Models tab click
**Source:** Part43

---

### TC-P3-095
**Category:** Feature
**Test Name:** Vision bottom tab shows vision sub-panel chip strip
**Steps:**
1. On mobile viewport, tap the Vision tab
**Expected Result:** Strip shows: Classifier, Processing, Detection, Segment chips
**Automation Hint:** `page.locator('[class*="mobile-strip"]')` — assert contains text "Classifier", "Processing"
**Source:** Part43

---

### TC-P3-096
**Category:** Feature
**Test Name:** Tools bottom tab opens slide-up sheet
**Steps:**
1. On mobile viewport, tap the Tools tab
**Expected Result:** A slide-up bottom sheet animates into view showing: Train New Model, SHAP Analyzer, Live Metrics options
**Automation Hint:** `page.locator('.tools-sheet')` — assert `isVisible()` after Tools tab click
**Source:** Part43

---

### TC-P3-097
**Category:** Feature
**Test Name:** Tools sheet closes when clicking the overlay
**Steps:**
1. On mobile viewport, open the Tools sheet
2. Click/tap the dark overlay area behind the sheet
**Expected Result:** The sheet slides back down and the overlay disappears
**Automation Hint:** `page.locator('.tools-sheet-overlay').click()` — assert `.tools-sheet` is hidden
**Source:** Part43

---

### TC-P3-098
**Category:** Backend API
**Test Name:** `GET /drift/{model_id}` returns correct schema with no predictions
**Steps:**
1. Send `GET /drift/diabetes` when prediction buffer is empty
**Expected Result:** Response is 200 JSON with keys: `n_recent`, `overall_score`, `overall_level`, `baseline`, `features[]`; `n_recent` is 0
**Automation Hint:**
```python
def test_drift_empty_buffer(client):
    resp = client.get('/drift/diabetes')
    assert resp.status_code == 200
    data = resp.json()
    assert 'overall_level' in data
    assert data['n_recent'] == 0
```
**Source:** Part43

---

### TC-P3-099
**Category:** Backend API
**Test Name:** `GET /drift/{model_id}` drift level is one of low/medium/high
**Steps:**
1. Make several predictions for `diabetes` model, then call `GET /drift/diabetes`
**Expected Result:** `overall_level` in response is one of: `"low"`, `"medium"`, `"high"`
**Automation Hint:**
```python
def test_drift_level_valid(client):
    resp = client.get('/drift/diabetes')
    assert resp.json()['overall_level'] in ('low', 'medium', 'high')
```
**Source:** Part43

---

### TC-P3-100
**Category:** Backend API
**Test Name:** `POST /drift/{model_id}/upload` accepts CSV and returns drift analysis
**Steps:**
1. Send `POST /drift/diabetes/upload` with a valid CSV matching the diabetes schema columns
**Expected Result:** Response 200 JSON with `source: "upload"`, `filename` field, and `features[]` list with numeric drift scores
**Automation Hint:**
```python
def test_drift_upload(client):
    csv_content = 'Pregnancies,Glucose (mg/dL),...\n2,130,...\n'
    resp = client.post('/drift/diabetes/upload',
                       files={'file': ('test.csv', csv_content, 'text/csv')})
    assert resp.status_code == 200
    assert resp.json()['source'] == 'upload'
```
**Source:** Part43

---

### TC-P3-101
**Category:** Backend API
**Test Name:** `POST /drift/{model_id}/upload` returns 400 for CSV with missing required columns
**Steps:**
1. Send `POST /drift/diabetes/upload` with a CSV missing required columns (e.g., only 2 of 8 columns)
**Expected Result:** Response is HTTP 400 (not 500); plain English error message
**Automation Hint:**
```python
def test_drift_upload_bad_csv(client):
    resp = client.post('/drift/diabetes/upload',
                       files={'file': ('bad.csv', 'wrong,columns\n1,2\n', 'text/csv')})
    assert resp.status_code in (400, 422)
```
**Source:** Part43

---

### TC-P3-102
**Category:** Feature
**Test Name:** Drift tab present in model view (4th tab)
**Steps:**
1. Open ML Unified, select any model
2. Check the tab bar
**Expected Result:** "Drift" tab is visible alongside Predict, Pipeline, What-if
**Automation Hint:** `page.locator('[class*="tab"]')` — assert 4 tabs total, one contains "Drift"
**Source:** Part43

---

### TC-P3-103
**Category:** Feature
**Test Name:** Drift tab shows mode toggle (From predictions / Upload dataset)
**Steps:**
1. Open ML Unified, select Diabetes model, click Drift tab
**Expected Result:** A segmented control is visible at the top with two options: "From predictions" and "Upload dataset"
**Automation Hint:** `page.locator('.drift-mode-bar')` — assert visible; assert 2 child `.drift-mode-btn` elements
**Source:** Part43

---

### TC-P3-104
**Category:** Feature
**Test Name:** Drift summary card shows SVG icon (not emoji) for overall level
**Steps:**
1. Open ML Unified, select a model, go to Drift tab
2. Switch to Upload dataset mode, upload a valid CSV
**Expected Result:** The summary card shows an SVG icon for the overall drift level: green checkmark (low), amber wave line (medium), red alert circle (high) — no emoji characters
**Automation Hint:** `page.locator('.drift-summary svg')` — assert visible; no emoji in textContent
**Source:** Part43

---

### TC-P3-105
**Category:** Feature
**Test Name:** Drift tab shows per-feature numeric drift rows
**Steps:**
1. Upload a valid CSV in Drift tab for Diabetes model
**Expected Result:** Each feature (Pregnancies, Glucose, etc.) shows a drift score bar + expected mean ± std vs recent mean ± std
**Automation Hint:** `page.locator('.drift-feature')` — assert count >= 5 (one per numeric feature)
**Source:** Part43

---

### TC-P3-106
**Category:** Feature
**Test Name:** Drift tab shows per-feature categorical bars for categorical features
**Steps:**
1. Upload a valid CSV in Drift tab for Titanic model
**Expected Result:** For categorical features (Sex, Pclass, Embarked), grouped bars show reference vs recent distribution per option
**Automation Hint:** `page.locator('.drift-cat-bar-ref')` — assert visible; `page.locator('.drift-cat-bar-recent')` — assert visible
**Source:** Part43

---

### TC-P3-107
**Category:** Feature
**Test Name:** Drift baseline uses training mean/std from StandardScaler (not schema midpoint)
**Steps:**
1. Send `GET /drift/diabetes` (or upload CSV)
2. Check per-feature "Expected" values in the drift response
**Expected Result:** Expected mean is the actual training distribution mean (e.g., ~120 mg/dL for Glucose), NOT the midpoint of the schema range [0, 200] = 100
**Automation Hint:**
```python
def test_drift_baseline_from_scaler(client):
    resp = client.get('/drift/diabetes')
    features = resp.json()['features']
    glucose_feat = next(f for f in features if 'glucose' in f['name'].lower())
    # Training mean should NOT equal midpoint of [0, 200]
    assert glucose_feat['ref_mean'] != 100.0
```
**Source:** Part44

---

### TC-P3-108
**Category:** Feature
**Test Name:** Drift footer note says "Numeric baseline from training data" when pipeline stats used
**Steps:**
1. Upload a valid CSV in Drift tab
2. Check the footer note text
**Expected Result:** Footer shows "Numeric baseline from training data", NOT "Numeric baseline estimated from field ranges"
**Automation Hint:** `page.locator('[class*="drift-footer"]')` — assert contains "from training data"
**Source:** Part44

---

### TC-P3-109
**Category:** Feature
**Test Name:** Drift footer shows row count from uploaded CSV
**Steps:**
1. Upload a CSV with 50 rows in Drift tab
2. Check the footer note
**Expected Result:** Footer shows "50 rows from filename.csv"
**Automation Hint:** After upload, `page.locator('[class*="drift-footer"]')` — assert contains "50 rows"
**Source:** Part44

---

### TC-P3-110
**Category:** Feature
**Test Name:** Drift response includes PSI badge per feature
**Steps:**
1. Upload a CSV via Drift tab for Titanic model
2. Inspect per-feature rows
**Expected Result:** Each feature shows a PSI badge — green (PSI < 0.10), amber (0.10–0.25), or red (> 0.25) — alongside the drift score
**Automation Hint:** `page.locator('[class*="psi-badge"]')` — assert count >= number of features
**Source:** Part45

---

### TC-P3-111
**Category:** Backend API
**Test Name:** `POST /drift/{model_id}/upload` response includes `psi` per feature
**Steps:**
1. POST a valid CSV to `/drift/diabetes/upload`
**Expected Result:** Each item in `features[]` has a `psi` field (float)
**Automation Hint:**
```python
def test_drift_psi_present(client):
    resp = client.post('/drift/diabetes/upload',
                       files={'file': ('test.csv', csv_data, 'text/csv')})
    features = resp.json()['features']
    for f in features:
        assert 'psi' in f
        assert isinstance(f['psi'], float)
```
**Source:** Part45

---

### TC-P3-112
**Category:** Feature
**Test Name:** Drift response includes KS test stat and p-value for upload mode
**Steps:**
1. Upload a CSV in Drift tab (upload mode only)
2. Inspect per-feature numeric rows
**Expected Result:** KS stat and p-value displayed: e.g., "KS stat: 0.234 · p-value: 0.018 — significant"
**Automation Hint:** `page.locator('[class*="ks-stat"]')` — assert visible and contains numeric values
**Source:** Part45

---

### TC-P3-113
**Category:** Feature
**Test Name:** Drift shows distribution histogram UI per numeric feature (upload mode)
**Steps:**
1. Upload a CSV in Drift tab
2. Inspect per numeric feature card
**Expected Result:** A mini 12-bin bar chart shows expected (grey) vs actual (accent color) distribution with a legend
**Automation Hint:** `page.locator('[class*="drift-hist"]')` — assert visible with bar elements
**Source:** Part45

---

### TC-P3-114
**Category:** Backend API
**Test Name:** Titanic drift uses actual training cat frequencies (not uniform)
**Steps:**
1. Upload a CSV to `/drift/titanic/upload`
2. Inspect reference distribution for Sex feature
**Expected Result:** Reference distribution for Sex shows training frequencies: male ~64.76%, female ~35.24% (NOT uniform 50/50)
**Automation Hint:**
```python
def test_drift_cat_freq_titanic(client):
    resp = client.post('/drift/titanic/upload',
                       files={'file': ('test.csv', csv_data, 'text/csv')})
    features = resp.json()['features']
    sex_feat = next(f for f in features if f['name'].lower() == 'sex')
    male_ref = sex_feat['categories']['male']['ref']
    assert abs(male_ref - 0.6476) < 0.01
```
**Source:** Part45

---

### TC-P3-115
**Category:** Feature
**Test Name:** Drift trend sparkline shown above feature list
**Steps:**
1. Use Drift tab multiple times (generate history entries)
2. Revisit Drift tab
**Expected Result:** An SVG sparkline is visible above the feature list; the line color reflects the latest drift level (green/amber/red)
**Automation Hint:** `page.locator('[class*="drift-trend"] svg')` — assert visible
**Source:** Part45

---

### TC-P3-116
**Category:** Feature
**Test Name:** Drift shows missing value (null rate) badge for features with nulls
**Steps:**
1. Upload a CSV where some values in one column are empty/null
2. View Drift tab results
**Expected Result:** The affected feature shows a red "X% null" badge next to the feature name
**Automation Hint:** `page.locator('[class*="null-badge"]')` — assert visible for column with nulls
**Source:** Part45

---

### TC-P3-117
**Category:** Backend API
**Test Name:** `GET /drift/{model_id}/history` returns last 20 snapshots
**Steps:**
1. Call `GET /drift/diabetes` at least 3 times to build history
2. Call `GET /drift/diabetes/history`
**Expected Result:** Response contains an array `trend[]` with timestamped snapshots; length <= 20
**Automation Hint:**
```python
def test_drift_history(client):
    for _ in range(3):
        client.get('/drift/diabetes')
    resp = client.get('/drift/diabetes/history')
    assert resp.status_code == 200
    assert len(resp.json()['trend']) >= 3
```
**Source:** Part45

---

### TC-P3-118
**Category:** E2E
**Test Name:** SSE progress bar shows during model training (POST /train)
**Steps:**
1. Open ML Unified Train wizard
2. Upload a CSV and configure a model
3. Click Train
4. Observe the UI during training
**Expected Result:** A progress bar appears showing training progress (0–100%) with stage messages like "CSV parse", "fit model", "evaluate"; bar has shimmer animation
**Automation Hint:** `page.locator('[class*="sse-progress"]')` — assert visible during training; `page.locator('[class*="sse-progress-fill"]')` — assert width increases
**Source:** Part45

---

### TC-P3-119
**Category:** E2E
**Test Name:** SSE progress bar shows during SHAP computation
**Steps:**
1. Open ML Unified, select a model
2. Run a prediction
3. Expand Feature Impact (SHAP)
**Expected Result:** A progress bar appears while SHAP values are being computed, showing stages: "Preprocess", "Compute SHAP values", "Aggregate features"
**Automation Hint:** `page.locator('[class*="sse-progress"]')` — assert visible while SHAP loads
**Source:** Part45

---

### TC-P3-120
**Category:** Backend API
**Test Name:** `POST /train` streams SSE progress events and final result
**Steps:**
1. POST to `/train` with a valid CSV and config
**Expected Result:** Response is `text/event-stream`; emits events with `{"pct": N, "msg": "..."}` pattern; final event has `{"done": true, "result": {...}}`
**Automation Hint:**
```python
def test_train_sse_stream(client, csv_data):
    with client.stream('POST', '/train', files=..., data=...) as resp:
        events = list(parse_sse(resp))
    assert events[-1]['done'] is True
    assert 'result' in events[-1]
```
**Source:** Part45

---

### TC-P3-121
**Category:** Backend API
**Test Name:** `POST /unsupervised` streams SSE progress events
**Steps:**
1. POST to `/unsupervised` with a valid CSV (k-means config)
**Expected Result:** SSE stream emits progress events; final event has `done: true` and plot data in `result`
**Automation Hint:** Same `_sse_result()` helper pattern; assert `result` contains plot/cluster data
**Source:** Part45

---

### TC-P3-122
**Category:** Backend API
**Test Name:** `POST /shap/{model_id}` streams SSE progress events
**Steps:**
1. Run a prediction for Diabetes model
2. POST to `/shap/diabetes` with input values
**Expected Result:** SSE stream emits progress: "Preprocess", "Compute SHAP values", "Aggregate"; final event has SHAP values per feature
**Automation Hint:** `_sse_result(response)` — assert `result['features']` is a non-empty list
**Source:** Part45

---

### TC-P3-123
**Category:** Backend API
**Test Name:** Validation errors before streaming return HTTP 400 (not 200 + SSE error)
**Steps:**
1. POST `/train` with a malformed CSV (wrong MIME type or empty file)
**Expected Result:** Response is HTTP 400 with plain English error; NOT a 200 with error buried in the SSE stream
**Automation Hint:**
```python
def test_train_invalid_returns_400(client):
    resp = client.post('/train', files={'file': ('bad.csv', b'', 'text/csv')}, data={})
    assert resp.status_code in (400, 422)
```
**Source:** Part45

---

### TC-P3-124
**Category:** Bug-Regression
**Test Name:** ml-vision Object Detection works on first request (no retry needed)
**Steps:**
1. Open ML Unified Vision — Object Detection
2. Upload an image
3. Click Detect (first time)
**Expected Result:** Detection results appear on the FIRST attempt, not after 2–3 retries; no timeout or empty result on first call
**Automation Hint:** `page.locator('[class*="detect-result"]')` — assert visible within 15s of first click; check no retry behavior in network tab
**Source:** Part48

---

### TC-P3-125
**Category:** Bug-Regression
**Test Name:** ml-vision Image Segmentation works on first request (no retry needed)
**Steps:**
1. Open ML Unified Vision — Image Segmentation
2. Upload an image and run segmentation (first time)
**Expected Result:** Segmentation result appears on the FIRST attempt without retry
**Automation Hint:** Same pattern as TC-P3-124 for segmentation endpoint
**Source:** Part48

---

### TC-P3-126
**Category:** Bug-Regression
**Test Name:** Iris SHAP Feature Impact shows non-zero values (LinearExplainer with zero background)
**Steps:**
1. Open ML Unified, select Iris Species Classifier
2. Fill sample values, click Predict
3. Expand Feature Impact panel
**Expected Result:** Feature Impact bars show non-zero SHAP values for each feature — NOT all zeros; Petal Length should have a large positive or negative contribution
**Automation Hint:** After SHAP loads, `page.locator('.shap-bar')` — evaluate width of bars; assert at least one bar has width > 5px
**Source:** Part48

---

### TC-P3-127
**Category:** Bug-Regression
**Test Name:** Iris model labeled as "Logistic Regression" not "Random Forest"
**Steps:**
1. Open ML Unified, select Iris Species Classifier
2. Inspect the model type label in the header
**Expected Result:** Model type eyebrow shows "Logistic Regression", not "Random Forest"
**Automation Hint:** `page.locator('.model-eyebrow')` — assert contains "Logistic Regression"
**Source:** Part48

---

### TC-P3-128
**Category:** Feature
**Test Name:** 6 themes available in ML Unified theme picker
**Steps:**
1. Open ML Unified
2. Click the theme picker dropdown in the navbar
**Expected Result:** 6 theme options with swatches: Dark, Light, Midnight, Ocean, Sunset, Forest
**Automation Hint:** `page.locator('[class*="theme-option"]')` — assert count === 6
**Source:** Part48

---

### TC-P3-129
**Category:** Feature
**Test Name:** Midnight theme applies black background
**Steps:**
1. Open ML Unified
2. Select the Midnight theme
**Expected Result:** Page background becomes `#000000` (pure black); accent colors shift to purple/pink/red
**Automation Hint:** After theme select, `page.evaluate(() => getComputedStyle(document.body).backgroundColor)` — assert `rgb(0, 0, 0)`
**Source:** Part48

---

### TC-P3-130
**Category:** Feature
**Test Name:** Forest theme applies dark green background with green accent
**Steps:**
1. Open ML Unified
2. Select the Forest theme
**Expected Result:** Background shifts to `#020f05` (near-black green); accent is green/emerald/cyan
**Automation Hint:** After theme select, `page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent-from'))` — assert green value
**Source:** Part48

---

### TC-P3-131
**Category:** Feature
**Test Name:** Theme persists to localStorage and URL `?theme=` param works
**Steps:**
1. Open ML Unified at `/?theme=midnight`
**Expected Result:** Midnight theme is applied immediately without user interaction
**Automation Hint:** Navigate to `?theme=midnight` — assert body background is `rgb(0,0,0)`
**Source:** Part48

---

### TC-P3-132
**Category:** Feature
**Test Name:** Training metrics show F1 and ROC-AUC chips for classifiers
**Steps:**
1. Open ML Unified Train wizard
2. Upload a CSV and train a classification model
3. Observe training result metrics
**Expected Result:** Result shows at minimum: Accuracy (main metric) + F1 (weighted) chip + ROC-AUC (macro OvR) chip
**Automation Hint:** `page.locator('[class*="metric-chip"]')` — assert count >= 2; assert text includes "F1" and "ROC"
**Source:** Part48

---

### TC-P3-133
**Category:** Feature
**Test Name:** Training metrics show MAE and RMSE chips for regressors (no R²)
**Steps:**
1. Train a regression model via the Train wizard
2. Observe training result metrics
**Expected Result:** Result shows MAE (main) + RMSE chip; R² is NOT shown
**Automation Hint:** `page.locator('[class*="metric-chip"]')` — assert contains "MAE" and "RMSE"; assert does NOT contain "R²"
**Source:** Part48

---

### TC-P3-134
**Category:** Animation
**Test Name:** SSE progress bar fill has shimmer animation (CSS ::after sweep)
**Steps:**
1. Trigger any long-running operation (train, SHAP, unsupervised)
2. Observe the progress bar fill during loading
**Expected Result:** A white shimmer sweep animation is visible moving across the progress bar fill
**Automation Hint:** `page.locator('.sse-progress-fill')` — assert CSS animation property is set; visual regression test
**Source:** Part48

---

### TC-P3-135
**Category:** Feature
**Test Name:** Semantic CSS variables used for drift badge colors (not hardcoded hex)
**Steps:**
1. Open ML Unified, go to Drift tab, upload CSV
2. Switch to Midnight theme
3. Observe drift badge colors
**Expected Result:** Drift badges (low/medium/high) use theme-aware semantic colors (`--color-success`, `--color-warning`, `--color-danger`) that adapt to the theme; NOT hardcoded hex values
**Automation Hint:** In Midnight theme, `.drift-badge--low` background-color should match `--color-success` var value
**Source:** Part48

---

### TC-P3-136
**Category:** Bug-Regression
**Test Name:** Model selection does NOT override theme accent color
**Steps:**
1. Open ML Unified, select Forest theme (green accent)
2. Select Titanic model (normally sky-blue accent)
3. Observe theme accent elements (gradient top bar, tab underline, logo gradient)
**Expected Result:** Theme accent stays green (Forest); Titanic model selection does NOT change the gradient top bar or tab underline to sky blue
**Automation Hint:** After Titanic select, `page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--accent-from'))` — assert green value, NOT sky blue
**Source:** Part50

---

### TC-P3-137
**Category:** Bug-Regression
**Test Name:** `--model-accent` and `--active-accent` are separate from `--accent`
**Steps:**
1. Select Forest theme, then select Titanic model
2. Check model-specific elements (sidebar dot, eyebrow) vs theme elements (top bar, tabs)
**Expected Result:** Sidebar dot and model eyebrow color use `--active-accent` (Titanic's sky blue); gradient top bar and tab underline use `--accent-from` (Forest green) — they differ
**Automation Hint:** `--active-accent` should be sky blue, `--accent-from` should be Forest green when Forest theme + Titanic model selected
**Source:** Part50

---

### TC-P3-138
**Category:** Bug-Regression
**Test Name:** EDA spinner visible in dark theme (not invisible)
**Steps:**
1. Open ML Unified in default dark theme, go to EDA mode
2. Upload a CSV and trigger analysis (observe spinner during loading)
**Expected Result:** The EDA loading spinner is clearly visible on the dark background; fill color uses `--color-success` (green), track uses `var(--border2)` (not invisible `--color-success-bg`)
**Automation Hint:** During loading, `page.locator('[class*="eda-spinner"]')` — assert visible and not blending with background
**Source:** Part50

---

### TC-P3-139
**Category:** Bug-Regression
**Test Name:** Light theme cards are monochromatic blue-gray (not stark white)
**Steps:**
1. Open ML Unified, switch to Light theme
2. Observe model cards and result cards
**Expected Result:** Cards use `#eef2f8` (blue-gray tinted) background, NOT stark `#ffffff` white that appears disconnected from the `#dce4f0` page background
**Automation Hint:** `page.locator('.model-header')` — computed background-color should be `rgb(238, 242, 248)`, NOT `rgb(255, 255, 255)`
**Source:** Part50

---

### TC-P3-140
**Category:** Bug-Regression
**Test Name:** Feature Impact panel does NOT show a `+` SVG icon in the header
**Steps:**
1. Open ML Unified, run a prediction
2. Expand Feature Impact (SHAP) panel
3. Inspect the panel header
**Expected Result:** The SHAP panel header shows only the title text — no `+` SVG icon or button is present
**Automation Hint:** `page.locator('[class*="shap-header"] svg[class*="plus"]')` — assert count === 0; or assert heading text content does not include `+`
**Source:** Part50

---

### TC-P3-141
**Category:** Bug-Regression
**Test Name:** No orange accent ring on cards in non-sunset themes (ring removed)
**Steps:**
1. Open ML Unified in Light theme
2. Select Insurance model (amber/orange accent)
3. Observe model header card border/outline
**Expected Result:** No orange-colored ring or outline appears on the model header card; the ring was removed to prevent model color bleeding into theme
**Automation Hint:** `page.locator('.model-header')` — assert `outline` and `box-shadow` do NOT contain orange/amber color values
**Source:** Part50

---

### TC-P3-142
**Category:** Feature
**Test Name:** Confidence bar predicted class uses gradient fill
**Steps:**
1. Open ML Unified, select Iris classifier
2. Run a prediction
3. Inspect the top confidence bar
**Expected Result:** The predicted class bar has a gradient fill (`linear-gradient(90deg, accent@53%, accent solid)`) rather than a flat color
**Automation Hint:** `page.locator('[class*="conf-bar--predicted"]')` — assert `background-image` contains `linear-gradient`
**Source:** Part50

---

### TC-P3-143
**Category:** Feature
**Test Name:** Non-predicted confidence bars are at reduced opacity (visually subordinate)
**Steps:**
1. Run a classification prediction with multiple classes
2. Inspect non-predicted class bars
**Expected Result:** Non-predicted bars have ~20% opacity fill, clearly subordinate to the predicted bar
**Automation Hint:** `page.locator('[class*="conf-bar"]:not([class*="predicted"])').first()` — assert `opacity` or fill opacity is <= 0.25
**Source:** Part50

---

### TC-P3-144
**Category:** Feature
**Test Name:** Drift SVG icons use `currentColor` (theme-aware, not hardcoded)
**Steps:**
1. Switch ML Unified to Midnight theme
2. Go to Drift tab and upload a CSV
3. Observe the drift level SVG icons
**Expected Result:** SVG icons adapt to the Midnight theme color scheme via `currentColor` + CSS class color rules; not hardcoded green/amber/red hex
**Automation Hint:** `page.locator('.drift-icon--low')` — assert `color` is the `--color-success` value for Midnight theme
**Source:** Part50

---

### TC-P3-145
**Category:** Feature
**Test Name:** JS error boxes use CSS class `.js-err-box` (theme-aware, not inline red)
**Steps:**
1. Trigger an error in ML Unified (e.g., upload invalid file format)
2. Observe the error message display
**Expected Result:** Error box uses `.js-err-box` CSS class styling that adapts to the current theme, rather than hardcoded inline `color: red`
**Automation Hint:** `page.locator('.js-err-box')` — assert visible on error; assert `background-color` uses `--color-danger-bg` value
**Source:** Part50

---

### TC-P3-146
**Category:** Backend API
**Test Name:** `POST /predict/{model_id}` returns prediction for all 4 built-in models
**Steps:**
1. POST valid sample inputs to: `/predict/diabetes`, `/predict/titanic`, `/predict/iris`, `/predict/insurance`
**Expected Result:** Each returns 200 with a `result` field containing the prediction; no 500 errors
**Automation Hint:**
```python
@pytest.mark.parametrize("model_id,payload", [
    ("diabetes", {...}), ("titanic", {...}), ("iris", {...}), ("insurance", {...})
])
def test_predict_all_models(client, model_id, payload):
    resp = client.post(f'/predict/{model_id}', json=payload)
    assert resp.status_code == 200
    assert 'result' in resp.json()
```
**Source:** Referenced across parts 36–50

---

### TC-P3-147
**Category:** Backend API
**Test Name:** `GET /pipeline/{model_id}` returns data for all 4 built-in models
**Steps:**
1. GET `/pipeline/diabetes`, `/pipeline/titanic`, `/pipeline/iris`, `/pipeline/insurance`
**Expected Result:** All 4 return 200 with valid pipeline step data
**Automation Hint:**
```python
@pytest.mark.parametrize("model_id", ["diabetes", "titanic", "iris", "insurance"])
def test_pipeline_all_models(client, model_id):
    resp = client.get(f'/pipeline/{model_id}')
    assert resp.status_code == 200
```
**Source:** Part41

---

### TC-P3-148
**Category:** Backend API
**Test Name:** `POST /shap/{model_id}` returns non-zero SHAP values for all 4 models
**Steps:**
1. POST valid inputs to `/shap/diabetes`, `/shap/titanic`, `/shap/iris`, `/shap/insurance`
**Expected Result:** Each returns SHAP feature contributions; at least one feature has a non-zero value
**Automation Hint:**
```python
@pytest.mark.parametrize("model_id,payload", [...])
def test_shap_nonzero(client, model_id, payload):
    result = _sse_result(client.post(f'/shap/{model_id}', json=payload))
    assert any(abs(f['value']) > 0 for f in result['features'])
```
**Source:** Part48, Part50

---

### TC-P3-149
**Category:** Data
**Test Name:** Drift score per feature is normalized 0–1 (not unbounded)
**Steps:**
1. Upload a wildly out-of-distribution CSV to any drift endpoint
**Expected Result:** All numeric drift scores in `features[]` are between 0.0 and 1.0 inclusive
**Automation Hint:**
```python
def test_drift_score_bounded(client):
    resp = client.post('/drift/diabetes/upload', files=...)
    for f in resp.json()['features']:
        if f['type'] == 'numeric':
            assert 0.0 <= f['drift_score'] <= 1.0
```
**Source:** Part43

---

### TC-P3-150
**Category:** Data
**Test Name:** PSI threshold boundaries: less than 0.10 = stable, 0.10–0.25 = caution, greater than 0.25 = unstable
**Steps:**
1. Craft CSVs that result in known PSI values and upload
**Expected Result:** `psi_level` in response is "stable" when psi < 0.10, "caution" when 0.10–0.25, "unstable" when > 0.25
**Automation Hint:**
```python
def test_psi_thresholds(client):
    # Upload minimally-drifted data -> psi_level 'stable'
    # Upload heavily-drifted data -> psi_level 'unstable'
    pass  # Parametrize with boundary-value CSVs
```
**Source:** Part45
