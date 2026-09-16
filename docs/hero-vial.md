# Interactive hero vial

The BPC-157 hero uses a real, parametric 3D model with the original full label wrapped onto its cylindrical body. The model is adapted from `render/scene.html`; it has a rounded glass heel and shoulder, a rubber stopper, crimped silver seal, grey flip-off cap, and white lyophilized contents. The original product photograph remains the loading and failure fallback.

## Sources and maintenance

- Graph product: `Product:BPC-157 10mg` — clear 3 mL vial, lyophilized powder; high confidence.
- Graph artwork: `Asset:inbox/labels/BPC-157-10mg_label.png` — high confidence. Astro imports this exact file into a hashed public asset; there is no duplicated or redrawn label.
- Label height: 16.5 mm, following the existing brand imagery specification; wrap width follows the source artwork's aspect ratio.
- `web/src/components/HeroVial.astro` owns progressive loading, accessibility, and layout.
- `web/src/scripts/vial-model.js` owns geometry and materials. Dimensions are in millimetres and follow the existing rendering model, not a new physical measurement of packaging.
- `web/src/scripts/hero-vial.js` owns lighting, camera, interaction, and resource cleanup. It reuses the repository's vendored MIT-licensed Three.js build. No new dependency or external asset host is required.
- The homepage only mounts this model for the matching BPC-157 SKU, avoiding a mismatched label if the featured product changes.

## Behavior and performance

Drag horizontally to rotate through the full label; mouse dragging also tilts the vial. Vertical touch scrolling remains available. Keyboard arrows rotate and tilt; Home and Reset view return to the initial pose. Reduced-motion preference disables interpolation and fades. No automatic spinning is used.

The renderer loads dynamically near the viewport. Pixel ratio is capped at 1.75, the studio environment is baked once, and rendering stops when the scene settles, leaves the viewport, or the page is hidden. Observers, listeners, geometries, textures, materials, and renderer resources are released during cleanup. A missing texture, renderer initialization failure, or lost graphics context leaves the product photo visible and hides unavailable controls.

The separate renderer bundle exceeds Vite's 500 kB warning threshold before transfer compression. It is only imported by the homepage's visible model; other pages do not load it. Lighthouse and physical mobile-device GPU performance were not measured.

## Validation

- Production build passed, including Cloudflare prerender.
- Graph ingest and validation passed; 21 Python tests passed.
- In-app browser: visual inspection at desktop and mobile sizes; no document overflow at 320, 390, and 1440 px.
- Drag rotation, arrow-key rotation, and reset verified in the browser.
- Temporary local fixtures verified no-JavaScript, missing-label, and lost-WebGL-context fallbacks. Each retained the photograph and hid the controls; the canvas was excluded from accessibility when unavailable. Fixtures are not part of source or deployment output.
- Browser console showed no errors during normal rendering. The missing-label fixture produced the expected fallback warning.

This change is a branch preview; it has not been deployed.
