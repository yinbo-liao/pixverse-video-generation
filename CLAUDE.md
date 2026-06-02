# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project: PixVerse Video Generation (Professional Practice)

This is a greenfield project to build an **expert-level AI video generation system** that integrates [PixVerse V6](https://pixverse.ai) (commercial video generation API) with [Semantic-Canvas](https://github.com/yinbo-liao/Semantic-Canvas) (diffusion-language-model prompt optimizer) to produce broadcast-quality, multi-shot narrative videos.

**Strategic goal**: Semantic-Canvas translates high-level narrative concepts into optimized, structured prompts that PixVerse V6 renders with significantly higher fidelity — achieving character consistency, scene progression, and thematic coherence across multi-clip sequences.

## Repository State

- **Current**: Pre-implementation. Contains only sample PixVerse output videos (MP4) and the professional guideline document. No application code yet.
- **Reference**: `PixVerse_AI_Professional_Guideline.md` — authoritative PixVerse V6 capability spec, prompt engineering framework, and production workflow guide
- **Upstream dependency**: [Semantic-Canvas](git@github.com:yinbo-liao/Semantic-Canvas.git) — operational FastAPI backend (Python 3.10+, FastAPI, SQLAlchemy 2.0 async, Pydantic v2) with React/Vite frontend scaffold

## Environment

```bash
# Python 3.11.9 venv (already exists)
.venv/Scripts/activate

# Install dependencies (when requirements are added)
pip install -r requirements.txt
```

## Architecture (Planned)

This project is a **middleware + orchestration layer** between two external systems:

```
┌─────────────────────┐      ┌──────────────────────────┐      ┌─────────────────┐
│   Semantic-Canvas   │ ──── │  PixVerse Bridge (THIS)  │ ──── │  PixVerse V6 API│
│  (prompt optimizer) │      │                          │      │  (video engine) │
│                     │      │  • Prompt schema adaption │      │                 │
│  REST + WebSocket   │      │  • Multi-shot chainer    │      │  REST / CLI     │
│  /v1/generate       │      │  • Parameter injection   │      │                 │
│  /v1/style-transfer │      │  • Feedback loop         │      │                 │
│  /v1/encode         │      │  • Session orchestration │      │                 │
│  /v1/diff           │      │  • Output QA assessment  │      │                 │
└─────────────────────┘      └──────────────────────────┘      └─────────────────┘
```

### Semantic-Canvas API Contract (what we consume)

| Endpoint | Method | Purpose for PixVerse |
|----------|--------|---------------------|
| `/v1/generate` | POST | Convert narrative concepts → structured video prompts |
| `/v1/ws/generate/{id}` | WS | Stream prompt refinement in real-time |
| `/v1/style-transfer` | POST | Adapt prompts to target visual styles |
| `/v1/encode` | POST | Generate latent embeddings for prompt comparison |
| `/v1/diff` | POST | Compute semantic distance between prompt variants |
| `/v1/regenerate-block` | POST | Block-level prompt regeneration (preserves context) |

Key Semantic-Canvas concepts applicable to PixVerse:
- **Style as latent vector arithmetic**: `formality`, `enthusiasm`, `technical_depth` sliders (0.0–1.0) control tone without rewriting prompts
- **LoRA constraint adapters**: Brand voice/style adapters merged at request time — analogous to PixVerse "character/preset style" anchoring
- **Semantic hash deduplication**: Identical prompt requests hit cache — enables cost-efficient prompt validation before generation
- **WebSocket streaming**: Progressive prompt refinement with partial previews at each denoising step

### PixVerse V6 Capability Summary

From `PixVerse_AI_Professional_Guideline.md`:

- **15-second single-pass 1080p** with built-in multi-shot engine and native audio synthesis
- **LPD Method** (Literal Physical Description): `[Subject] + [Action/Motion] + [Environment] + [Lighting] + [Camera/Lens] + [Audio]`
- **Anchor-Repeat Protocol**: Repeat core physical descriptors across shots for consistency
- **Reference Images**: Up to 7 images for character/product anchoring
- **Model tiers**: V6 Standard (testing), V6 Pro (delivery), Turbo/540p (preview, ~60% credit savings)
- **Credit pricing**: ~23 credits/sec for 1080p+audio; $1 = 200 credits; ~15s commercial ≈ $1.73

### Integration Strategy (Phased Build Plan)

**Phase 1 — API Bridge**: Middleware that translates Semantic-Canvas `GenerateResponse` → PixVerse prompt schema. Implements the LPD template structure with field mapping: `sketch_notes` → environment/lighting context, `style` → motion/camera parameters, `constraints` → anchor descriptors.

**Phase 2 — Multi-Shot Chainer**: Orchestrates Anchor-Repeat Protocol across shot sequences. Uses Semantic-Canvas `/v1/encode` to compute latent embeddings for each shot prompt, then `/v1/diff` to measure semantic drift between shots. Flags shots exceeding a divergence threshold for re-prompting.

**Phase 3 — Feedback Loop**: Analyzes PixVerse output (temporal stability, artifact presence, prompt adherence) and feeds findings back to Semantic-Canvas for iterative prompt refinement. Uses the 3-Generation Rule (Variation A baseline, B +10% motion, C -10% motion).

**Phase 4 — Advanced Features**:
- **Dynamic Parameter Injection**: Semantic-Canvas style vectors map to PixVerse motion strength, camera parameters, lens selections
- **Multi-Concept Fusion**: Combine multiple Semantic-Canvas outputs into single cohesive PixVerse generation
- **Adaptive Prompt Tuning**: Learning agent that adjusts prompt parameters based on output quality metrics

## PixVerse Prompt Template (Target Schema)

The bridge must transform Semantic-Canvas structured output into PixVerse LPD format:

```
[Subject description from constraints.must_include]
[Action/Motion derived from style.enthusiasm → motion intensity mapping]
[Environment from sketch_notes]
[Lighting from constraints.tone parsing]
[Camera/Lens from style.formality → camera formality mapping]
[Audio from prompt audio cues]
```

## Testing Protocol (Per Phase)

Each phase must validate:
1. **API communication**: Semantic-Canvas ↔ Bridge ↔ PixVerse connectivity
2. **Prompt fidelity**: Semantic-Canvas output correctly translates to PixVerse prompt schema
3. **Output quality**: Compare against baseline PixVerse results
4. **Cost efficiency**: Credit usage tracking per generation cycle
5. **Artifact audit**: Check for motion smearing, facial drift, lighting inconsistency, temporal flicker (see guideline §8)

Quantitative metrics: Prompt adherence score, motion smoothness, semantic drift between shots.
Qualitative metrics: Narrative flow, visual appeal, character consistency.

## Key Files

- `PixVerse_AI_Professional_Guideline.md` — PixVerse V6 full capability spec, prompt engineering, QA protocols
- Sample outputs in root: `PixVerse_V6_*.mp4`, `PixVerse_Pixverse-c1_*.mp4` — baseline quality references

## Upstream Reference: Semantic-Canvas

Located at `git@github.com:yinbo-liao/Semantic-Canvas.git`. Key architectural facts:

- **Model backend**: Configurable via `MODEL_BACKEND` env var — `local` (PyTorch GPU), `triton` (NVIDIA Triton), `fallback` (OpenAI/Claude API — default, no GPU needed)
- **DB**: PostgreSQL + asyncpg, Alembic migrations, Redis for latent cache (24h TTL)
- **Auth**: JWT with bcrypt, refresh token rotation
- **Dev workflow**: `uvicorn app.main:app --reload --port 8000`, `pytest` (with `pytest-asyncio`, coverage via `pytest-cov`)
- **Lint/format**: `ruff` (line-length 100), `black` (line-length 100), `mypy` (strict mode)
- **Frontend stack**: React 18 + Vite 5 + TypeScript 5 + Tailwind 3 + Zustand + Three.js (not yet built)

### Semantic-Canvas Inference Pipeline (Reference)

```
Input Text → VAE Encoder (~300M) → latent [seq_len, 64]
           → DiT Denoiser (~2B, 12-24 steps, DPM-Solver++) + LoRA merge
           → VAE Decoder (~300M) → Output Text
```

Style vectors (formality, enthusiasm, technical_depth) applied as weighted shifts directly in latent space — zero additional inference cost.
