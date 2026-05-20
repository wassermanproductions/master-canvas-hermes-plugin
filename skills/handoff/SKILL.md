---
name: handoff
description: Work with Master Canvas AI video handoff packages. Use when a user provides a Master Canvas ZIP or project_manifest.json and wants Hermes to inspect assets, preserve scene and shot order, prepare ComfyUI/LTX 2.3 jobs, or hand off prompts to Kling, Veo, or another video generation operator.
version: 1.0.0
author: Wasserman Productions
license: MIT
platforms: [macos, linux, windows]
metadata:
  hermes:
    tags: [media, video, comfyui, ltx, veo, kling, handoff]
---

# Master Canvas Handoff

Use this skill when a user gives Hermes a Master Canvas handoff ZIP, extracted package folder, or `project_manifest.json` and wants video-generation work planned or executed from that package.

## Default Workflow

1. Inspect the package with `mastercanvas_inspect_package`.
2. If the package is a ZIP and generation work will happen locally, extract it with `mastercanvas_extract_package`.
3. Build the ComfyUI/LTX plan with `mastercanvas_comfy_plan`.
4. Treat `project_manifest.json` as the source of truth for scene order, shot order, prompts, negative prompts, references, and output bins.
5. Keep outputs organized by scene using `deliverables/bin_plan.json` or the `outputBin` fields in the plan.

## Package Contract

Expected Master Canvas handoff packages usually contain:

- `project_manifest.json`: complete project context, scene list, shot list, asset list, prompt fields, negative prompt fields, and generation targets.
- `assets/`: source images, uploaded video references, uploaded music/audio references, and other media.
- `comfyui/jobs/`: one JSON job per shot when exported by Master Canvas.
- `kling-veo/`: prompt sheets for operators using hosted generation tools.
- `hermes-agent/`: agent-facing brief and context notes.
- `deliverables/bin_plan.json`: target folder/bin structure for completed renders.

If one of these folders is missing, continue with the manifest and explain the limitation.

## ComfyUI / LTX 2.3 Execution Guidance

When the user wants ComfyUI/LTX:

- Preserve the shot sequence exactly.
- Use the image path from `sourceImage` as the first-frame/image reference for each shot.
- Use the provided prompt and negative prompt without dropping lens, lighting, action, continuity, or sound notes.
- Target at least 1080p unless the manifest specifies a higher floor.
- Generate each shot into its scene bin.
- Return an inventory of completed shots grouped by scene.
- Flag missing assets, impossible prompt requirements, or continuity conflicts before starting expensive generation.

## Kling / Veo Operator Guidance

When the user wants Kling, Veo, or a human operator handoff:

- Use the Kling/Veo prompt sheet if present.
- Otherwise build a simple table with scene, shot order, source asset path, prompt, negative prompt, duration, and notes.
- Keep file names and output bins stable so rendered clips can be reconciled against the original canvas.

## Verification

Before reporting completion:

- Confirm total scenes and shots.
- Confirm whether any shots are missing source images.
- Confirm where extracted assets or output bins are located.
- Summarize the next concrete generation step.
