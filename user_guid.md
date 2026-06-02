# PixVerse Bridge — User Guide

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Architecture](#architecture)
4. [API Reference](#api-reference)
   - [1. Generate (Single Prompt)](#1-generate-single-prompt)
   - [2. Shot Sequence (Multi-Shot)](#2-shot-sequence-multi-shot)
   - [3. Feedback Loop (3-Generation Rule)](#3-feedback-loop-3-generation-rule)
   - [4. Parameter Injection](#4-parameter-injection)
   - [5. Concept Fusion](#5-concept-fusion)
   - [6. Production Pipeline (All-in-One)](#6-production-pipeline-all-in-one)
5. [The LPD Prompt Format](#the-lpd-prompt-format)
6. [Style Vectors Reference](#style-vectors-reference)
7. [Artifact Types & Fixes](#artifact-types--fixes)
8. [PixVerse V6 Parameter Presets](#pixverse-v6-parameter-presets)
9. [Configuration](#configuration)
10. [Testing](#testing)
11. [Production Workflow Examples](#production-workflow-examples)

---

## Overview

**PixVerse Bridge** is a middleware service that translates narrative concepts into optimized video generation prompts for [PixVerse V6](https://pixverse.ai). It integrates with [Semantic-Canvas](https://github.com/yinbo-liao/Semantic-Canvas) — a diffusion-language-model prompt optimizer — to produce broadcast-quality, multi-shot narrative videos with automatic artifact detection and refinement.

**What it does:**
- Takes your narrative idea (e.g., "a detective walking through a rainy neon alley")
- Optimizes it through an AI prompt refinement pipeline
- Decomposes it into PixVerse V6's LPD (Literal Physical Description) format
- Generates multi-shot sequences with character consistency
- Detects and fixes common AI video artifacts before generation
- Maps creative style choices to precise camera, motion, and lighting parameters
- Estimates credit cost before you spend anything

**Key capabilities:**
- **6 API endpoints** covering single-shot, multi-shot, artifact analysis, parameter injection, concept fusion, and full production pipeline
- **Mock mode** for offline development — no external APIs required
- **Deterministic** — same input always produces same output (critical for iteration)
- **179 tests**, zero lint errors

---

## Quick Start

### Prerequisites

- Python 3.11+
- Windows, macOS, or Linux

### Installation

```powershell
# Clone the repository
git clone <repo-url> pixverse-video
cd pixverse-video

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -e ".[dev]"

# Copy environment config
copy .env.example .env      # Windows
# cp .env.example .env       # macOS/Linux
```

### Start the server

```powershell
uvicorn app.main:app --port 8001 --reload
```

The server starts at **http://localhost:8001** with mock mode enabled by default. In mock mode, all prompts are optimized using deterministic algorithms — no external API keys needed.

### Quick test

```powershell
curl -X POST http://localhost:8001/v1/bridge/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "A steaming cup of coffee on a wooden table at sunrise"}'
```

### Swagger documentation

Open **http://localhost:8001/docs** in your browser for interactive API documentation.

---

## Architecture

```
                        PixVerse Bridge (this project)
                        ┌────────────────────────────────┐
  Narrative Concept ──→ │                                │
                        │  ┌──────────────────────────┐  │
  Style Vectors ──→     │  │   Semantic-Canvas Client  │  │     PixVerse V6
  (formality,           │  │   (prompt optimization)   │──┼──→  API
   enthusiasm,          │  └──────────────────────────┘  │     (video
   technical_depth)     │                                │     generation)
                        │  ┌──────────────────────────┐  │
  Constraints ──→       │  │   Prompt Transformer      │  │
  (tone, keywords)      │  │   (LPD decomposition)     │  │
                        │  └──────────────────────────┘  │
                        │                                │
  Sketch Notes ──→      │  ┌──────────────────────────┐  │
  (world context)       │  │   Artifact Analyzer       │  │
                        │  │   (6 artifact detectors)  │  │
                        │  └──────────────────────────┘  │
                        │                                │
                        │  ┌──────────────────────────┐  │
                        │  │   Parameter Injector      │  │
                        │  │   (style → V6 params)     │  │
                        │  └──────────────────────────┘  │
                        └────────────────────────────────┘
```

**6 endpoints, 5 phases:**

| Phase | Endpoint | Purpose |
|-------|----------|---------|
| 1 | `/v1/bridge/generate` | Single LPD prompt generation |
| 2 | `/v1/bridge/shot-sequence` | Multi-shot with drift analysis |
| 3 | `/v1/bridge/feedback-loop` | 3-Generation Rule + artifact refinement |
| 4 | `/v1/bridge/parameter-injection` | Style vectors → PixVerse V6 parameters |
| 4 | `/v1/bridge/concept-fusion` | Blend 2-5 concepts into unified scene |
| 5 | `/v1/bridge/production-pipeline` | Full end-to-end workflow |

---

## API Reference

### 1. Generate (Single Prompt)

**`POST /v1/bridge/generate`**

Transforms a narrative concept into a PixVerse V6 LPD prompt.

**Request:**

```json
{
  "prompt": "A cyberpunk detective walks through a rainy neon-lit street",
  "sketch_notes": "Narrow alley in future Tokyo. Holographic signs. Steam rising from grates.",
  "constraints": {
    "tone": "noir",
    "must_include": ["cyberpunk detective", "trench coat", "neon reflections"],
    "must_exclude": ["daylight", "crowds"]
  },
  "style": {
    "formality": 0.8,
    "enthusiasm": 0.7,
    "technical_depth": 0.6
  },
  "generation_params": {
    "num_steps": 12,
    "temperature": 0.8
  }
}
```

**Response:**

```json
{
  "generation_id": "mock-abc123",
  "original_prompt": "A cyberpunk detective walks through a rainy neon-lit street",
  "optimized_text": "A cyberpunk detective in a weathered trench coat strides through...",
  "lpd_prompt": {
    "subject": {"description": "cyberpunk detective, trench coat, and neon reflections"},
    "action_motion": {"description": "dynamic", "motion_strength": 0.7},
    "environment": {"description": "Narrow alley in future Tokyo. Holographic signs..."},
    "lighting": {"description": "high-contrast noir lighting, dramatic shadows"},
    "camera_lens": {"description": "professional tracking", "formality": 0.8},
    "audio": {"description": "subtle ambient atmosphere, low drones"}
  },
  "lpd_text": "cyberpunk detective, trench coat, and neon reflections. dynamic. Narrow alley...",
  "metadata": {"sc_metadata": {...}, "cached": false}
}
```

**Field descriptions:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `prompt` | string | Yes | Core narrative concept (1-4096 chars) |
| `sketch_notes` | string | No | World context, setting details (up to 65536 chars) |
| `constraints.tone` | string | No | Lighting mood: noir, warm, cold, golden, neon, soft, dramatic, etc. |
| `constraints.must_include` | list | No | Keywords that MUST appear in the prompt |
| `constraints.must_exclude` | list | No | Keywords to avoid |
| `style.formality` | float | No | Camera formality: 0.0=handheld, 0.5=standard, 1.0=cinematic |
| `style.enthusiasm` | float | No | Motion intensity: 0.0=static, 0.5=natural, 1.0=explosive |
| `style.technical_depth` | float | No | Semantic detail level: 0.0=simple, 0.5=standard, 1.0=highly detailed |
| `generation_params.num_steps` | int | No | Denoising steps (4-24, default 12): higher = more coherent |
| `generation_params.temperature` | float | No | Output creativity (0.1-2.0, default 0.8) |

---

### 2. Shot Sequence (Multi-Shot)

**`POST /v1/bridge/shot-sequence`**

Generates a multi-shot sequence using the PixVerse V6 Anchor-Repeat Protocol — maintaining character/product consistency across wide, medium, and close-up shots with semantic drift analysis.

**Request:**

```json
{
  "anchor": "a silver Tesla Cybertruck",
  "base_prompt": "driving across a desert highway at sunset",
  "sketch_notes": "Vast desert. Cacti silhouettes. Dust trail behind vehicle.",
  "constraints": {"tone": "golden"},
  "style": {"formality": 0.8, "enthusiasm": 0.5},
  "shots": [
    {"shot_index": 0, "shot_type": "wide", "transition_notes": "Fade in from black"},
    {"shot_index": 1, "shot_type": "medium", "transition_notes": "Cut on action"},
    {"shot_index": 2, "shot_type": "close-up", "transition_notes": "Slow push-in"}
  ],
  "drift_threshold": 0.3
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `anchor` | Core subject that appears in EVERY shot (Anchor-Repeat Protocol) |
| `base_prompt` | Shared narrative foundation for all shots |
| `shots[].shot_type` | `wide` (establishing), `medium` (detail), or `close-up` (intimate) |
| `shots[].transition_notes` | How this shot transitions from the previous one |
| `shots[].style_overrides` | Per-shot style adjustments (overrides base style) |
| `drift_threshold` | Shots with semantic drift > this value are flagged (default 0.3) |

**Response includes:**

- Per-shot LPD prompts with complete BridgeResponse
- `drift_from_previous`: semantic distance from previous shot (null for first shot)
- `flagged`: true if drift exceeds threshold
- `coherence_score`: overall sequence coherence (1.0 = perfect)
- `flagged_shots`: list of shot indices needing re-prompting

**Shot type defaults:**

| Shot Type | Default Formality | Prompt Prefix |
|-----------|-------------------|---------------|
| `wide` | 0.5 | "Wide establishing shot:" |
| `medium` | 0.6 | "Medium detail shot:" |
| `close-up` | 0.7 | "Close-up shot:" |

---

### 3. Feedback Loop (3-Generation Rule)

**`POST /v1/bridge/feedback-loop`**

Implements the PixVerse V6 3-Generation Rule: generates 3 motion-strength variations of a prompt, analyzes each for 6 artifact types, iteratively refines flagged prompts, and selects the best variation.

**Request:**

```json
{
  "prompt": "A detective runs frantically through a flashing neon alley",
  "sketch_notes": "Narrow alley at night. Flashing neon signs.",
  "constraints": {"tone": "noir"},
  "style": {"enthusiasm": 0.7, "formality": 0.6},
  "max_iterations": 2,
  "refinement_mode": "auto"
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `max_iterations` | Max refinement cycles per variation (1-10, default 3) |
| `refinement_mode` | `auto` = apply fixes automatically; `manual` = report findings only |

**The 3 variations:**

| Variation | Motion Strength | Purpose |
|-----------|-----------------|---------|
| `baseline` | Original enthusiasm | Reference quality |
| `high_motion` | enthusiasm + 0.10 (max 1.0) | Test motion smearing risk |
| `low_motion` | enthusiasm - 0.10 (min 0.0) | Test temporal stability |

**Selection algorithm (composite score):**

- **50%** artifact cleanliness (`1.0 - risk_score`)
- **30%** temporal stability (`1.0 - max(motion, flicker severity)`)
- **20%** keyword coherence with original intent

**Response includes:**
- 3 `VariationResult` objects with full BridgeResponse per variation
- `artifact_report` per variation (findings, risk_score, is_clean)
- `refinement_history`: artifact snapshots at each iteration
- `selected_variation` with `selection_reason`

---

### 4. Parameter Injection

**`POST /v1/bridge/parameter-injection`**

Maps Semantic-Canvas style vectors to precise PixVerse V6 generation parameters with human-readable justifications. This tells you exactly what camera, lens, lighting, motion, and render settings to use.

**Request:**

```json
{
  "prompt": "A fashion model walks down a runway",
  "style": {"formality": 0.9, "enthusiasm": 0.3, "technical_depth": 0.8},
  "target_duration": 10,
  "aspect_ratio": "9:16"
}
```

**Response (key fields):**

```json
{
  "params": {
    "motion": {
      "strength_pct": 40,
      "speed_label": "relaxed natural pace",
      "acceleration": "smooth linear"
    },
    "camera": {
      "camera_type": "crane/jib",
      "lens_mm": 85,
      "stabilization": "counterweight crane",
      "movement": "crane up/down, sweeping arc, dramatic reveal"
    },
    "lighting": {
      "setup_name": "cinematic multi-point",
      "key_light": "booklight / cove diffusion",
      "fill_light": "negative fill for contrast control",
      "back_light": "multi-rim + practicals + eye light",
      "complexity": "8+ sources"
    },
    "render": {
      "tier": "cinematic",
      "model": "V6 Pro + C1",
      "upscale": "4K AI upscale pipeline"
    },
    "aspect_ratio": "9:16",
    "duration_seconds": 10
  },
  "justifications": {
    "motion": "enthusiasm=0.30 → relaxed natural pace at 40% strength",
    "camera": "formality=0.90 → crane/jib, 85mm lens, counterweight crane",
    "lighting": "technical_depth=0.80 → cinematic multi-point (8+ sources)",
    "render": "technical_depth=0.80 → cinematic tier: V6 Pro + C1, 4K AI upscale"
  }
}
```

**Aspect ratio options:**

| Value | Resolution | Best For |
|-------|-----------|----------|
| `9:16` | 1080×1920 | TikTok, Reels, Shorts, Stories |
| `1:1` | 1080×1080 | Instagram, Facebook, LinkedIn |
| `16:9` | 1920×1080 | YouTube, broadcast, web |
| `21:9` | 2560×1080 | Cinematic, film festival |

---

### 5. Concept Fusion

**`POST /v1/bridge/concept-fusion`**

Blends 2-5 independent narrative concepts into a single cohesive PixVerse scene. Each concept is assigned a spatial role (foreground/background/ambient) and blend weight.

**Request:**

```json
{
  "concepts": [
    {"prompt": "a sleek sports car", "role": "foreground", "weight": 1.2},
    {"prompt": "a neon-lit city at night", "role": "background", "weight": 0.8},
    {"prompt": "light rain and fog", "role": "ambient", "weight": 0.5}
  ],
  "unifying_theme": "cyberpunk street racing",
  "style": {"formality": 0.7, "enthusiasm": 0.8}
}
```

**Concept roles:**

| Role | Purpose | Example |
|------|---------|---------|
| `foreground` | Main subject, closest to camera | Character, product, vehicle |
| `background` | Setting, environment behind subject | City, landscape, room |
| `ambient` | Atmosphere, mood, lighting quality | Fog, rain, warm glow, dust |

**Weight guidance:**

| Weight | Effect |
|--------|--------|
| 0.1–0.5 | Trace influence, subtle presence |
| 0.5–1.0 | Equal contribution |
| 1.0–2.0 | Dominant, overpowers other concepts |

**Response includes:**
- `unified_prompt`: full BridgeResponse for the fused scene
- `concept_results`: each concept's individual optimized text
- `blend_coherence`: how well concepts blend (1.0 = seamless)
- `scene_composition`: spatial layout directive

---

### 6. Production Pipeline (All-in-One)

**`POST /v1/bridge/production-pipeline`**

Chains all phases into a single end-to-end workflow. This is the **recommended endpoint for production use**.

**Pipeline flow:**
```
Concept Fusion → Parameter Injection → Shot Sequence → Feedback Loop → Deliverable
```

**Request:**

```json
{
  "prompt": "A lone samurai walks through a bamboo forest at dawn",
  "sketch_notes": "Ancient bamboo forest. Mist rising. Golden dawn light.",
  "concepts": [
    {"prompt": "a weathered samurai in worn armor", "role": "foreground", "weight": 1.2},
    {"prompt": "misty bamboo forest with dappled light", "role": "background", "weight": 0.8}
  ],
  "unifying_theme": "solitude and discipline",
  "style": {"formality": 0.7, "enthusiasm": 0.3, "technical_depth": 0.6},
  "target_duration": 8,
  "aspect_ratio": "16:9",
  "shot_count": 3,
  "max_feedback_iterations": 1
}
```

**Key fields:**

| Field | Description |
|-------|-------------|
| `prompt` | Core narrative concept |
| `concepts` | Optional: 2-5 concepts to fuse (skips fusion if omitted) |
| `target_duration` | Video length in seconds (1-15) |
| `aspect_ratio` | Output aspect ratio |
| `shot_count` | Number of shots (2-12) |
| `max_feedback_iterations` | Refinement cycles (0 = skip feedback) |

**Response includes:**
- `fusion_result`: concept blending output (null if skipped)
- `parameter_result`: injected PixVerse V6 parameters
- `shot_sequence_result`: multi-shot sequence with drift analysis
- `feedback_result`: refinement output (null if iterations=0)
- `stages[]`: status and timing per pipeline stage
- `total_duration_ms`: total execution time
- `estimated_credits`: approximate PixVerse V6 credit cost
- `final_lpd_prompts[]`: prompts ready for PixVerse V6 submission

---

## The LPD Prompt Format

PixVerse V6 uses the **Literal Physical Description (LPD)** method. Every prompt is structured as 6 sequential components:

```
[Subject] + [Action/Motion] + [Environment] + [Lighting] + [Camera/Lens] + [Audio]
```

**Example LPD prompt:**
```
A silver Tesla Model 3 drives along a coastal highway at golden hour.
Wide aerial tracking shot. Ocean waves visible to the right.
Warm golden hour sunlight reflects off clean paintwork.
Camera tracks from above, 35mm lens.
Engine hum and wind noise.
```

**The 6 components:**

| Component | What it describes | Example phrases |
|-----------|-------------------|-----------------|
| **Subject** | Physical description of the main subject | "A silver Tesla Model 3", "Woman with auburn hair and teal blazer" |
| **Action/Motion** | What the subject does and how fast | "drives along", "turns head slowly", "sprints rapidly" |
| **Environment** | Setting, location, weather, time | "coastal highway at golden hour", "modern office lobby" |
| **Lighting** | Light quality, direction, color | "warm golden hour sunlight", "soft diffused light from window" |
| **Camera/Lens** | Camera movement, framing, lens | "wide aerial tracking shot", "medium close-up, shallow depth of field" |
| **Audio** | Sound design, music, ambience | "engine hum and wind noise", "gentle ambient electronic music" |

**The Anchor-Repeat Protocol:**
For multi-shot sequences, repeat the **exact same Subject descriptor** in every shot prompt. This is how PixVerse V6 maintains character and product consistency across shots.

---

## Style Vectors Reference

Three 0.0–1.0 sliders control creative direction. Each maps to specific PixVerse V6 parameters:

### Formality → Camera

| Value | Camera Type | Lens | Stabilization | Movement |
|-------|------------|------|---------------|----------|
| 0.00–0.15 | handheld | 24mm | none | verite wandering |
| 0.15–0.35 | shoulder-rig | 35mm | minimal | documentary float |
| 0.35–0.55 | tripod | 50mm | locked | smooth pan/tilt |
| 0.55–0.70 | slider/dolly | 50mm | damped | slow push, lateral |
| 0.70–0.85 | steadicam | 35mm | gimbal | orbiting, floating |
| 0.85–0.95 | crane/jib | 85mm | counterweight | sweeping arcs |
| 0.95–1.00 | technocrane | 135mm | 3-axis gyro | motion control |

### Enthusiasm → Motion

| Value | Strength | Speed | Acceleration |
|-------|----------|-------|-------------|
| 0.00–0.10 | 5% | static | none |
| 0.10–0.25 | 20% | slow motion | gentle ease-in |
| 0.25–0.45 | 40% | relaxed natural | smooth linear |
| 0.45–0.65 | 60% | steady purposeful | steady ramp |
| 0.65–0.85 | 80% | dynamic energetic | brisk snap |
| 0.85–1.00 | 100% | explosive rapid | instant peak |

### Technical Depth → Lighting + Render

| Value | Lighting Setup | Render Tier | Model |
|-------|---------------|-------------|-------|
| 0.00–0.20 | ambient natural | draft (540p) | V6 Standard |
| 0.20–0.40 | 2-point basic | standard (720p) | V6 Standard |
| 0.40–0.60 | 3-point standard | high (1080p) | V6 Pro |
| 0.60–0.80 | 3-point + accent | high (1080p) | V6 Pro |
| 0.80–1.00 | cinematic multi-point | cinematic (4K) | V6 Pro + C1 |

---

## Artifact Types & Fixes

The feedback loop detects 6 common AI video artifacts from prompt text analysis:

| Artifact | Detection Pattern | Severity | Automatic Fix |
|----------|------------------|----------|---------------|
| **Motion smearing** | High motion words + fast action verbs | 0.4–0.8 | Replace fast verbs, add "slow motion" |
| **Hand distortion** | Close-up framing + hand/finger words | 0.85 | Switch to medium shot |
| **Facial drift** | Multi-shot language, weak anchoring | 0.7 | Add repeated descriptors |
| **Lighting inconsistency** | Conflicting tone pairs (warm/cold, bright/dark) | 0.25/pair | Remove conflicting tone |
| **Subject blending** | Chaos/crowd words, no focus markers | 0.8 | Add "center-lock focus, shallow depth of field" |
| **Temporal flicker** | Strobe/flicker/flash keywords | 0.4–0.9 | Replace with stable terms |

**How to avoid artifacts in your prompts:**
- Keep motion strength moderate (0.4–0.6) for smooth output
- Avoid close-up + hand detail combinations
- Repeat subject descriptors across multi-shot prompts
- Use consistent lighting language throughout
- Add focus markers for complex/busy scenes
- Avoid strobe, flicker, and rapid-light-change words

---

## PixVerse V6 Parameter Presets

### Camera Profiles

| Profile | Lens | Best For |
|---------|------|----------|
| Handheld | 24mm | Documentary, POV, gritty realism |
| Shoulder-rig | 35mm | Run-and-gun, event coverage |
| Tripod | 50mm | Interviews, product shots, static |
| Slider/Dolly | 50mm | Smooth reveals, product showcases |
| Steadicam | 35mm | Tracking shots, walking scenes |
| Crane/Jib | 85mm | Establishing shots, dramatic reveals |
| Technocrane | 135mm | Hollywood cinematic, motion control |

### Lighting Setups

| Setup | Sources | Best For |
|-------|---------|----------|
| Ambient natural | 1 | Outdoor, documentary, casual |
| 2-point basic | 2 | YouTube, talking head, simple |
| 3-point standard | 3 | Commercial, interview, portrait |
| 3-point + accent | 5 | Product, fashion, high-end |
| Cinematic multi-point | 8+ | Film, broadcast, premium commercial |

### Render Tiers

| Tier | Model | Resolution | Credit Cost/sec | Best For |
|------|-------|-----------|-----------------|----------|
| Draft | V6 Standard | 540p | ~12 | Prompt testing, iteration |
| Standard | V6 Standard | 720p | ~18 | Social media, quick delivery |
| High | V6 Pro | 1080p | ~23 | Commercial, broadcast |
| Cinematic | V6 Pro + C1 | 4K upscale | ~35 | Premium, film festival |

---

## Configuration

### `.env` file reference

```ini
# Semantic-Canvas upstream service
SEMANTIC_CANVAS_BASE_URL=http://localhost:8000   # SC service URL
SEMANTIC_CANVAS_API_KEY=                         # SC API key (if auth enabled)
SEMANTIC_CANVAS_TIMEOUT=30                       # Request timeout in seconds
SEMANTIC_CANVAS_MOCK=true                        # true = offline dev mode, no SC needed

# PixVerse V6
PIXVERSE_API_KEY=                                # For future direct PixVerse API integration

# Application
LOG_LEVEL=INFO                                   # DEBUG, INFO, WARNING, ERROR
DEBUG=true                                       # Enables /docs Swagger UI
```

### Running with a real Semantic-Canvas instance

1. Clone and set up Semantic-Canvas:
```powershell
git clone git@github.com:yinbo-liao/Semantic-Canvas.git
cd semantic-canvas-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements/dev.txt
cp .env.example .env
# Edit .env: set FALLBACK_API_KEY to your OpenAI/Anthropic key
uvicorn app.main:app --port 8000
```

2. Configure the bridge to use it:
```ini
# In pixverse-video/.env
SEMANTIC_CANVAS_MOCK=false
SEMANTIC_CANVAS_BASE_URL=http://localhost:8000
```

3. Start the bridge:
```powershell
uvicorn app.main:app --port 8001
```

---

## Testing

### Run all tests

```powershell
cd H:\pixverse-video
.venv\Scripts\activate
pytest -v
```

**Current: 179 tests passing across 8 test files:**

| Test file | Tests | Coverage |
|-----------|-------|----------|
| `test_prompt_transformer.py` | 59 | Motion, camera, tone mapping |
| `test_bridge_api.py` | 26 | Generate + shot-sequence + feedback endpoints |
| `test_shot_schemas.py` | 14 | Shot sequence schema validation |
| `test_shot_chainer.py` | 24 | Multi-shot chainer + mock embedding |
| `test_feedback_loop.py` | 41 | Detectors, fixes, refinement, selection |
| `test_phase4.py` | 13 | Presets, injection, fusion |
| `test_production_pipeline.py` | 5 | E2E pipeline |
| **Total** | **179** | |

### Run specific test file

```powershell
pytest tests/test_feedback_loop.py -v
pytest tests/test_shot_chainer.py -v
```

### Lint check

```powershell
ruff check app/ tests/
```

---

## Production Workflow Examples

### Example 1: E-Commerce Product Ad

```powershell
curl -X POST http://localhost:8001/v1/bridge/production-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A matte-black wireless headphone on a minimalist pedestal",
    "sketch_notes": "Clean white studio background. Subtle reflections on polished surface.",
    "style": {"formality": 0.6, "enthusiasm": 0.2, "technical_depth": 0.5},
    "target_duration": 5,
    "aspect_ratio": "1:1",
    "shot_count": 3,
    "max_feedback_iterations": 1
  }'
```

**Expected result:** 5-second product showcase with tripod camera, slow deliberate motion, 3-point lighting, standard render quality. ~345 credits.

### Example 2: Cinematic Short Film Scene

```powershell
curl -X POST http://localhost:8001/v1/bridge/production-pipeline \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A warrior stands at the edge of a cliff overlooking a burning village",
    "sketch_notes": "Medieval fantasy setting. Smoke rising from distant buildings. Storm clouds gathering.",
    "concepts": [
      {"prompt": "armored warrior with battle-worn shield", "role": "foreground", "weight": 1.5},
      {"prompt": "burning village in distant valley below", "role": "background", "weight": 0.8},
      {"prompt": "storm clouds and falling ash", "role": "ambient", "weight": 0.6}
    ],
    "unifying_theme": "aftermath of battle",
    "style": {"formality": 0.9, "enthusiasm": 0.1, "technical_depth": 0.9},
    "target_duration": 12,
    "aspect_ratio": "21:9",
    "shot_count": 3,
    "max_feedback_iterations": 2
  }'
```

**Expected result:** 12-second cinematic scene with crane/jib camera, static tableau motion, cinematic multi-point lighting, 4K upscale. ~1,656 credits.

### Example 3: Social Media Short

```powershell
curl -X POST http://localhost:8001/v1/bridge/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "A steaming cup of matcha latte on a wooden table",
    "sketch_notes": "Morning sunlight through window. Ceramic cup with latte art.",
    "constraints": {"tone": "soft"},
    "style": {"formality": 0.5, "enthusiasm": 0.05, "technical_depth": 0.3}
  }'
```

**Expected result:** Single-shot cozy coffee scene with tripod camera, near-static motion, soft diffused lighting. ~115 credits for 5 seconds.

### Example 4: Action Sports Highlight

```powershell
curl -X POST http://localhost:8001/v1/bridge/shot-sequence \
  -H "Content-Type: application/json" \
  -d '{
    "anchor": "a red mountain bike with rider in blue gear",
    "base_prompt": "descending a rocky trail through dense forest",
    "style": {"formality": 0.3, "enthusiasm": 0.85},
    "shots": [
      {"shot_index": 0, "shot_type": "wide", "transition_notes": "Drone establishing shot"},
      {"shot_index": 1, "shot_type": "medium", "transition_notes": "Fast whip pan"},
      {"shot_index": 2, "shot_type": "close-up", "transition_notes": "Hard cut to POV"},
      {"shot_index": 3, "shot_type": "wide", "transition_notes": "Slow-motion landing"}
    ],
    "drift_threshold": 0.4
  }'
```

**Expected result:** 4-shot action sequence. Check `flagged_shots` for any shots exceeding drift threshold. Refine flagged shots individually before final generation.

---

## Troubleshooting

### Server won't start

```powershell
# Check port is free
netstat -ano | findstr :8001

# Kill any lingering Python processes
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force
```

### Tests fail after changes

```powershell
# Clear Python cache and re-run
Get-ChildItem -Recurse -Filter __pycache__ | Remove-Item -Recurse -Force
pytest -v
```

### Mock mode not working

Check `.env`:
```ini
SEMANTIC_CANVAS_MOCK=true
```
Restart server after changing `.env`.

### Real Semantic-Canvas returns 401

Add your API key to Semantic-Canvas `.env`:
```ini
FALLBACK_API_KEY=sk-your-openai-key
```
Or set up Anthropic:
```ini
FALLBACK_API_TYPE=anthropic
FALLBACK_API_KEY=sk-ant-your-key
```

---

*PixVerse Bridge v0.1.0 — 5-Phase Production Pipeline*
*Built with FastAPI, Pydantic v2, Semantic-Canvas integration*
