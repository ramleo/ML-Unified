# Session 2026-08-17 — Depth Parallax: AR Occlusion & 3D Relief Fixes (Part 238)

Continuation of Part 237 (Depth Parallax tool build). This session picked up post-compaction with the 3D relief mesh already camera-shift-based and deployed, but with fresh live bug reports from the user's own screenshots.

## 0. Opening state

User showed a screenshot of the 3D relief view with a visible trapezoid/bowtie warp — the photo's own rectangular boundary was bowing in and out mid-peek-animation, reading as "warped/ugly" rather than 3D.

## 1. Relief mesh edge-warp fix

**Diagnosis**: the mesh displaced every vertex in Z by its depth value, including at the mesh's own outer boundary. Under perspective projection, a vertex pushed toward the camera projects larger and one pushed away projects smaller — so a straight photo edge with varying depth along it (e.g. sky vs. road at a corner) stops projecting as a straight line once the camera shifts off-center. The photo's own silhouette was warping, not just its interior.

**Fix**: added `edgeFeather()` to `reliefMesh.ts` — depth is smoothstep-tapered to zero over the outermost `EDGE_FEATHER_CELLS` grid cells on all four sides, so boundary vertices stay flat under any camera shift while the interior still bulges with real depth.

**Also**: user asked "why the homepage ui is not applied here" — traced to `ToolsAIChat`, present on 11 of 16 other tool pages but missing from `depth-parallax/page.tsx`. Added it with a tool-specific summary. Separately, `DepthParallaxRunner.tsx`'s cards still used the old flat `rgba()` card style that `text-to-image` itself had already moved away from — swapped to the same `Card` chrome as `ProjectCard.tsx` (homepage's "Live ML Apps" cards): `var(--bg-glass)` + backdrop blur + colored 3px accent top bar.

Commits: `94dfc48`, `a53bd1d` (bundled with next fix), `f50c54e`.

## 2. AR occlusion — three-attempt fix (the real story of this session)

User's screenshot showed the AR marker's bottom edge as jagged, torn-looking static where it overlapped a treeline — not a clean occlusion cutoff.

**Attempt 1 — blur the depth input (`a53bd1d`)**: blurred the depth texture used only for the occlusion decision (never the displayed image), same trick already used for the earlier parallax tearing fix. Reduced jaggedness but user's next screenshot showed the marker now *bleeding through* the tree — visible well inside where it should have been hidden.

**Root cause of the bleed-through**: averaging (blurring) always drags a thin near object (a branch) toward its much larger far neighbor (sky) — the exact opposite of what occlusion needs. A wide blur (7px, `9945d50`) smeared "far" values into a whole band of tree-boundary pixels, letting the marker show through gaps a real object has.

**Attempt 2 — soften with a wider fade band, shrink blur (`9945d50`, `4634ce1`)**: still fundamentally using averaged depth; better but the same lose-lose kept resurfacing — small blur → jagged, wide blur → bleed-through.

**Attempt 3 — the actual fix (`6512ca9`)**: replaced the CPU-side blurred-canvas approach entirely with a GPU max-filter sampled directly in the fragment shader (`nearestRealDepth()`, 5×5 taps, `KERNEL_STEP` UV offsets). Occlusion needs "is anything real near HERE" — a max, not a mean. A max-filter means any nearby near-content (a thin branch) wins outright instead of being diluted by the sky around it — a small, correct dilation of the true silhouette rather than a biased blur of it.

**Smoothness follow-up (`e0fda72`)**: user asked for the transition itself to look smoother. Since the max-filter (not the fade band) was now doing the bleed-through prevention, the depth-band fade and marker-edge falloff could be widened freely without reintroducing the earlier bug — these are independent knobs once decoupled correctly.

**Verified live via Playwright** (with explicit permission before starting the pass): uploaded the test Porsche photo to the deployed site, placed the marker at the treeline via synthetic pointer events, cropped/zoomed the canvas region from a full-page screenshot (`sips`/PIL crop, since element-screenshot selectors kept grabbing the wrong `<canvas>` — the page has two, a particle background canvas and the tool canvas). Confirmed: marker fades smoothly into the tree, properly hidden where the tree is nearer than the marker's assigned depth.

## 3. 3D relief "photo looks small" — two-attempt fix

User's screenshot showed the relief photo occupying only a small fraction of its own canvas, with a large dark dead-space border around it.

**Attempt 1 (`e0fda72`)**: narrowed `FOV_RAD` from 75° to 60°, reasoning that the near-plane margin (used for the zero-clip camera-shift guarantee) was overly conservative. **This was analytically wrong** — the near-plane margin formula only governs the few pixels that reach true maximum depth; the bulk of any photo (sky, road, background) sits near the *far/base* plane, whose fill barely changed (~65%→~67%). The photo still looked shrunk in the next screenshot.

**Attempt 2 (`2be899f`) — the real fix**: exported `EDGE_FEATHER_CELLS` from `reliefMesh.ts` and used it in `Relief3DCanvas.tsx`'s margin math — since full depth is *guaranteed* to never occur within that many cells of the mesh boundary (from the earlier edge-warp fix), the frustum-framing math only has to budget for the worst case *inside* that guaranteed-flat border (`worstCaseExtent = 1 - EDGE_FEATHER_CELLS / max(cols, rows)`), not the mesh's full spatial extent. This is a materially smaller, still-safe worst case. Retuned `CAMERA_DISTANCE` 2.6→2.4 and `FOV_RAD` 60°→52° together, and widened `EDGE_FEATHER_CELLS` 6→14 to give the new formula real margin to work with.

**Verified locally before pushing** (to avoid a third risky live-deploy cycle in the same area): started a local Next.js dev server, temporarily pointed `NEXT_PUBLIC_ML_UNIFIED_URL` at the real deployed HF Space backend (local backend wasn't running), uploaded the test photo, and confirmed via Playwright screenshots — fill went from ~65% to ~85% at rest, and a synthetic full-range drag confirmed no clipping at the shift extreme. Restored `.env.local` and killed the dev server before committing.

## Commits (ml-portfolio, all frontend-only — no HF Space upload needed)

1. `94dfc48` — relief mesh edge-feathering (warp fix) + missing `ToolsAIChat` widget
2. `a53bd1d` — AR occlusion depth blur (attempt 1)
3. `f50c54e` — card chrome matched to `text-to-image`/homepage `ProjectCard` style
4. `9945d50` — AR occlusion soft depth-band fade (attempt 2a)
5. `4634ce1` — AR occlusion blur shrink, bleed-through diagnosis (attempt 2b)
6. `6512ca9` — AR occlusion max-filter replacing blur entirely (real fix)
7. `e0fda72` — AR occlusion smoothness widen (correct) + 3D relief FOV narrow (wrong analysis)
8. `2be899f` — 3D relief framing fixed properly via edge-feather-aware margin math

## How to apply going forward

- **Occlusion/masking decisions from a noisy signal**: reach for a max/min-filter (dilation/erosion) before reaching for a blur. A blur is only correct when you want a *representative average*; a hard hide/show decision needs "is there anything extreme nearby," which a mean actively washes out. This cost three iterations to land on this session.
- **Frustum/framing math**: when reasoning about "does this fill the frame," check what the BULK of typical content is near (usually the far/base plane for a landscape photo), not just the worst-case extreme (near plane) — a margin formula can be perfectly safe and still not address the visible complaint if it optimizes the wrong plane.
- **Verify locally against the real backend before a second/third live-deploy iteration** in the same risky area (frustum clipping had already caused a real "went out of frame" incident earlier in Part 237) — a local dev server pointed at the deployed API caught the wrong-plane mistake before it cost another live-site round-trip.
- User's standing rule from Part 237 (ask before every individual Playwright action) was relaxed this session to "ask once before starting a verification pass, then run the whole pass" after the user said "how many times should i share ss?" — a signal that per-step confirmation had become the friction, not the safety net.
