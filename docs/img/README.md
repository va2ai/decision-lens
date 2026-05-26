# Screenshots and demo recording

The repo README references four images in this directory. They are not checked in yet — record them locally and commit the resulting files.

| File | What to capture |
|---|---|
| `demo.gif` | A 20–40 s end-to-end walkthrough: paste `data/sample_cases/case_001_administrative_denial.txt`, click **Analyze**, scroll through Issues → Findings → Citations → Flags, then click the **Trace** tab to show the span timeline. |
| `screenshot-results.png` | The Results page with at least one expanded finding showing a `CitationBadge` next to a supporting source id. |
| `screenshot-trace.png` | The `AgentTimeline` for a completed run — all six spans visible with durations and status dots. |
| `screenshot-evals.png` | The `EvalDashboard` reading from `evals/results/latest.json` with per-case rows. |

## Setup

```bash
# Backend
uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd web && npm install && npm run dev
```

Then open http://localhost:5173.

For the eval dashboard screenshot you'll need a `latest.json`. If you have an LLM key:

```bash
echo "OPENAI_API_KEY=sk-..." > .env
python scripts/run_evals.py
```

## Recording the GIF

Any of these works:

- **macOS / Linux / Windows:** [Peek](https://github.com/phw/peek) or [LICEcap](https://www.cockos.com/licecap/).
- **CLI:** record a `.mov`/`.mp4` with your OS recorder, then `ffmpeg -i in.mp4 -vf "fps=12,scale=1200:-1:flags=lanczos" -loop 0 demo.gif`.
- **Target size:** keep `demo.gif` under ~6 MB so GitHub renders it inline.

## Conventions

- 1200 px wide minimum so screenshots are readable in the README at full width.
- Light theme (the app's default).
- Use the synthetic `case_001_administrative_denial.txt` so nothing in the recording leaks real-looking data.
