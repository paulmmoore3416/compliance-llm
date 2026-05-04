# Frontend Guide

The Compliance-Llama UI is a small, single-page React app. The full source is ~600 lines of TypeScript.

---

## Stack

- **React 18** with hooks
- **TypeScript** strict mode
- **Tailwind CSS** for styling (no UI kit — we want a tight bundle)
- **react-markdown** + **remark-gfm** for SOP rendering (GitHub-flavored Markdown, including tables)
- **Vite** for dev/build

No state library. The app's state fits comfortably in `useState` hooks at the top of `App.tsx`.

---

## Running the dev server

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

The dev server proxies API calls based on `VITE_API_BASE_URL` (default `http://localhost:8080`). Override in `.env.local`:

```bash
VITE_API_BASE_URL=https://api.compliance-llama.example.com
```

Production build:

```bash
npm run build
npm run preview   # serve the built dist on :4173
```

The Docker image (`docker/Dockerfile.frontend`) runs the dev server, which is fine for hackathon/demo. For production-grade hosting, build with `npm run build` and serve `dist/` from a static host (Cloudflare Pages, S3, etc.).

---

## Component map

```
src/
├── App.tsx                       Top-level state + layout
├── components/
│   ├── Header.tsx                Logo, model badge, /health polling
│   ├── DeviceContextPanel.tsx    Left rail: device form + controls
│   └── OutputPanel.tsx           Right pane: streaming markdown + Copy/PDF
├── lib/
│   └── api.ts                    Typed API client incl. SSE parser
└── types/
    └── api.ts                    Shared types (mirror backend pydantic)
```

The split is intentional: one component per logical region of the screen, no nested abstraction.

### Streaming

`streamGenerate(req, onToken)` in `lib/api.ts` reads the response body as a `ReadableStream`, decodes UTF-8 chunks, and parses SSE frames manually. The browser's built-in `EventSource` would be nicer except it doesn't support POST bodies, which we need to send the request payload.

```typescript
const resp = await fetch(`${BASE}/v1/generate/stream`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
  body: JSON.stringify(req),
  signal,
});
const reader = resp.body!.getReader();
const decoder = new TextDecoder();
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  // … find "\n\n" frames, dispatch event/data …
}
```

The `signal` parameter is wired to an `AbortController` in `App.tsx` so a second click on Generate cancels the in-flight stream.

---

## Customizing

### Add a new artifact type

The list of available artifacts lives in three coordinated places:

1. **Backend enum** — [`backend/app/schemas.py`](../../backend/app/schemas.py): add to `ArtifactType` and `_INSTRUCTION_TEMPLATES`.
2. **Frontend type** — [`frontend/src/types/api.ts`](../../frontend/src/types/api.ts): add to the `ArtifactType` union.
3. **Frontend label** — [`frontend/src/components/DeviceContextPanel.tsx`](../../frontend/src/components/DeviceContextPanel.tsx): add to `ARTIFACT_LABELS`.

If you want the new artifact to be a *training* objective too (so the model learns its format), add a builder function to [`data/synthetic/build_dataset.py`](../../data/synthetic/build_dataset.py)'s `ARTIFACT_BUILDERS` list and re-train.

### Change the look

The Tailwind theme is in [`frontend/tailwind.config.js`](../../frontend/tailwind.config.js) under `theme.extend.colors.amd`. The default palette is dark-mode AMD-style. To rebrand, swap the hex values; nothing references `amd-red` etc. by name outside of Tailwind classes.

### Wire in a different backend

The whole API surface is in `lib/api.ts` and `types/api.ts`. Point `VITE_API_BASE_URL` elsewhere and as long as the new server speaks the same `/v1/generate*` shape, the UI works unchanged.

---

## Accessibility & UX notes

- The form is keyboard-navigable; all inputs are real `<input>`/`<select>`/`<textarea>` elements.
- The streaming pane uses `aria-live="polite"` *implicitly* via React updating text content; for stricter SR support you'd add it explicitly to the markdown container.
- Long outputs scroll independently; the form rail and output pane scroll on their own to keep the form visible.
- The "Compare with base Llama 3.1" button is disabled with a tooltip when the base endpoint isn't configured — no surprise 503s for the user.

---

## Known frontend limitations (hackathon scope)

- No persistence — refresh the page and you lose generated output. (A trivial localStorage shim would fix this.)
- No auth — anyone who can reach `:5173` can hit the API.
- No A11y audit — works with keyboard but hasn't been screen-reader tested.
- Mobile layout is unreviewed. The form/output split assumes ≥ 1024px wide.
