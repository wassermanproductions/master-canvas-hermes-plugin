# Master Canvas Hermes Plugin

Hermes Agent plugin for reading Master Canvas handoff packages and turning them into generation-ready plans for ComfyUI/LTX, Kling, Veo, or human operators.

Master Canvas is a local-first pre-production canvas for AI video projects. This plugin is the Hermes-facing companion: it does not generate video by itself, but it gives Hermes reliable tools for inspecting exports, extracting assets, and preserving scene/shot order during handoff.

## Install

```bash
hermes plugins install wassermanproductions/master-canvas-hermes-plugin --enable
```

Or install manually:

```bash
git clone https://github.com/wassermanproductions/master-canvas-hermes-plugin.git ~/.hermes/plugins/master-canvas
hermes plugins enable master-canvas
```

Restart Hermes after installing or enabling the plugin.

## Tools

- `mastercanvas_capabilities`: explains package structure and workflow.
- `mastercanvas_inspect_package`: summarizes scenes, shots, assets, references, target generation, and readiness.
- `mastercanvas_extract_package`: extracts a handoff ZIP into a local folder.
- `mastercanvas_comfy_plan`: returns a shot-by-shot ComfyUI/LTX execution plan.

## Bundled Skill

The plugin also registers a bundled skill:

```text
master-canvas:handoff
```

Use it when a user provides a Master Canvas ZIP or manifest and wants Hermes to preserve all project context for AI video generation.

## Example

```text
Use master-canvas:handoff with /path/to/master-canvas-handoff.zip.
Inspect it, extract it, build the ComfyUI/LTX plan, and organize outputs by scene.
```

## Source App

Master Canvas app:

https://github.com/wassermanproductions/master-canvas

## License

MIT
