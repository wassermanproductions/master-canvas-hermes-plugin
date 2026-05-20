"""Hermes handlers for Master Canvas handoff packages."""

from __future__ import annotations

import csv
import json
import mimetypes
import shutil
import uuid
import zipfile
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path


def _json(data):
    return json.dumps(data, indent=2)


def _error(message: str, **extra):
    payload = {"success": False, "error": message}
    payload.update(extra)
    return _json(payload)


def _resolve(path: str) -> Path:
    return Path(path).expanduser().resolve()


def _read_manifest(package_path: str) -> tuple[dict, Path, bool]:
    path = _resolve(package_path)
    if path.is_dir():
        manifest_path = path / "project_manifest.json"
        return json.loads(manifest_path.read_text(encoding="utf-8")), path, False
    if path.name == "project_manifest.json":
        return json.loads(path.read_text(encoding="utf-8")), path.parent, False
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            with archive.open("project_manifest.json") as handle:
                return json.loads(handle.read().decode("utf-8")), path, True
    raise ValueError(f"Unsupported Master Canvas package: {path}")


def _manifest_write_target(package_path: str) -> tuple[dict, Path, Path]:
    manifest, source, is_zip = _read_manifest(package_path)
    if is_zip:
        raise ValueError("Cannot modify a ZIP in place. Extract it first, then update the extracted folder.")
    manifest_path = source / "project_manifest.json" if source.is_dir() else source
    return manifest, manifest_path.parent, manifest_path


def handle_capabilities(_args=None, **_kwargs):
    return _json(
        {
            "success": True,
            "toolset": "mastercanvas",
            "workflow": [
                "To autonomously build a project, use mastercanvas_create_package from a brief, scenes, shots, and optional asset paths.",
                "Use mastercanvas_upsert_scene and mastercanvas_upsert_shot to keep refining the package as the user gives new direction.",
                "Use mastercanvas_package_zip when the package is ready to share or send to another operator.",
                "Use mastercanvas_inspect_package on existing handoff ZIPs before generation.",
                "Use mastercanvas_extract_package to unpack assets and job files.",
                "Use mastercanvas_comfy_plan to get a shot-by-shot LTX/ComfyUI execution plan.",
                "Hand the extracted comfyui/jobs files to the ComfyUI tool/plugin, or use the kling-veo prompt sheets for hosted generators.",
            ],
            "package_contract": [
                "project_manifest.json is the source of truth.",
                "assets/ contains source images, video references, music references, and other media.",
                "comfyui/jobs contains one JSON job per shot.",
                "kling-veo/ contains human-readable prompt sheets for hosted generation tools.",
                "deliverables/bin_plan.json defines scene bins for returned renders.",
            ],
            "autonomous_tools": [
                "mastercanvas_create_package",
                "mastercanvas_upsert_scene",
                "mastercanvas_upsert_shot",
                "mastercanvas_package_zip",
            ],
            "bundled_skill": "Load skill_view('master-canvas:handoff') for the recommended operator workflow.",
        }
    )


def handle_create_package(args, **_kwargs):
    try:
        output_dir = _resolve(args["output_dir"])
        overwrite = bool(args.get("overwrite", False))
        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            return _error(
                "output_dir exists and is not empty; pass overwrite=true to replace it",
                output_dir=str(output_dir),
            )
        if output_dir.exists() and overwrite:
            shutil.rmtree(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        manifest = _build_manifest(args)
        _copy_assets_for_manifest(output_dir, manifest)
        _write_package_files(output_dir, manifest)
        zip_path = ""
        if args.get("zip"):
            zip_path = str(_write_zip(output_dir, overwrite=True))
    except Exception as exc:
        return _error(str(exc), output_dir=args.get("output_dir"))

    return _json(
        {
            "success": True,
            "package_dir": str(output_dir),
            "zip_path": zip_path,
            "manifest": str(output_dir / "project_manifest.json"),
            "scene_count": len(manifest.get("scenes", [])),
            "shot_count": len(manifest.get("shots", [])),
        }
    )


def handle_upsert_scene(args, **_kwargs):
    try:
        manifest, package_dir, _manifest_path = _manifest_write_target(args["package_path"])
        scene = _normalize_scene(args["scene"], len(manifest.get("scenes", [])) + 1)
        scenes = manifest.setdefault("scenes", [])
        index = _find_scene_index(scenes, scene["sceneKey"])
        if index >= 0:
            existing_shots = scenes[index].get("shots", [])
            scenes[index].update({key: value for key, value in scene.items() if key != "shots" or value})
            if not scene.get("shots"):
                scenes[index]["shots"] = existing_shots
        else:
            scenes.append(scene)
        _resequence_manifest(manifest)
        _write_package_files(package_dir, manifest)
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"))

    return _json({"success": True, "package_dir": str(package_dir), "scene": scene["sceneKey"]})


def handle_upsert_shot(args, **_kwargs):
    try:
        manifest, package_dir, _manifest_path = _manifest_write_target(args["package_path"])
        shot = _normalize_shot(args["shot"], len(manifest.get("shots", [])) + 1)
        _ensure_scene(manifest, shot["sceneKey"])
        _attach_asset_to_shot(package_dir, shot, manifest)
        _upsert_shot_in_manifest(manifest, shot)
        _resequence_manifest(manifest)
        _write_package_files(package_dir, manifest)
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"))

    return _json(
        {
            "success": True,
            "package_dir": str(package_dir),
            "scene": shot["sceneKey"],
            "orderLabel": shot["orderLabel"],
            "sourcePath": shot.get("sourcePath", ""),
        }
    )


def handle_package_zip(args, **_kwargs):
    try:
        package_dir = _resolve(args["package_path"])
        if package_dir.name == "project_manifest.json":
            package_dir = package_dir.parent
        if not package_dir.is_dir():
            return _error("package_path must be an extracted package folder or project_manifest.json")
        zip_path = _resolve(args["zip_path"]) if args.get("zip_path") else package_dir.with_suffix(".zip")
        if zip_path.exists() and not args.get("overwrite", False):
            return _error("zip_path already exists; pass overwrite=true to replace it", zip_path=str(zip_path))
        _write_zip(package_dir, zip_path=zip_path, overwrite=True)
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"))

    return _json({"success": True, "zip_path": str(zip_path)})


def handle_inspect_package(args, **_kwargs):
    try:
        manifest, source, is_zip = _read_manifest(args["package_path"])
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"))

    scenes = manifest.get("scenes", [])
    shots = manifest.get("shots", [])
    missing_assets = [shot for shot in shots if not shot.get("sourcePath")]
    return _json(
        {
            "success": True,
            "source": str(source),
            "source_type": "zip" if is_zip else "folder_or_manifest",
            "title": manifest.get("title"),
            "schema": manifest.get("schema"),
            "scene_count": len(scenes),
            "shot_count": len(shots),
            "asset_count": len(manifest.get("assets", [])),
            "reference_count": len(manifest.get("references", [])),
            "target_generation": manifest.get("targetGeneration", {}),
            "scene_bins": [
                {
                    "scene": scene.get("sceneKey"),
                    "shot_count": len(scene.get("shots", [])),
                    "output_bin": f"renders/{_scene_folder(scene.get('sceneKey', 'scene'))}",
                }
                for scene in scenes
            ],
            "missing_source_paths": [
                {"orderLabel": shot.get("orderLabel"), "title": shot.get("title")}
                for shot in missing_assets
            ],
            "ready": len(missing_assets) == 0,
        }
    )


def handle_extract_package(args, **_kwargs):
    try:
        package_path = _resolve(args["package_path"])
        output_dir = _resolve(args["output_dir"])
        overwrite = bool(args.get("overwrite", False))

        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            return _json(
                {
                    "success": False,
                    "extracted": False,
                    "reason": "output_dir exists and is not empty; pass overwrite=true to replace files",
                    "output_dir": str(output_dir),
                }
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        if zipfile.is_zipfile(package_path):
            with zipfile.ZipFile(package_path) as archive:
                archive.extractall(output_dir)
        elif package_path.is_dir():
            for child in package_path.iterdir():
                target = output_dir / child.name
                if child.is_dir():
                    if target.exists() and overwrite:
                        shutil.rmtree(target)
                    shutil.copytree(child, target, dirs_exist_ok=overwrite)
                else:
                    shutil.copy2(child, target)
        else:
            return _error("package_path must be a ZIP or extracted package folder")
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"), output_dir=args.get("output_dir"))

    return _json({"success": True, "extracted": True, "output_dir": str(output_dir)})


def handle_comfy_plan(args, **_kwargs):
    try:
        manifest, source, _is_zip = _read_manifest(args["package_path"])
    except Exception as exc:
        return _error(str(exc), package_path=args.get("package_path"))

    shots = manifest.get("shots", [])
    return _json(
        {
            "success": True,
            "source": str(source),
            "title": manifest.get("title"),
            "engine": "ComfyUI",
            "model": manifest.get("targetGeneration", {}).get("model", "LTX 2.3 image-to-video"),
            "quality_floor": manifest.get("targetGeneration", {}).get("minimumResolution", "1080p"),
            "shot_count": len(shots),
            "shots": [
                {
                    "orderLabel": shot.get("orderLabel"),
                    "scene": shot.get("sceneKey"),
                    "sourceImage": shot.get("sourcePath"),
                    "outputBin": shot.get("outputBin"),
                    "duration": shot.get("duration"),
                    "resolution": shot.get("resolution"),
                    "prompt": shot.get("prompt"),
                    "negativePrompt": shot.get("negativePrompt"),
                    "notes": shot.get("notes"),
                }
                for shot in shots
            ],
        }
    )


def _build_manifest(args):
    scenes_input = args.get("scenes") or []
    flat_shots = list(args.get("shots") or [])
    scenes = []
    for index, scene_data in enumerate(scenes_input, start=1):
        scene = _normalize_scene(scene_data, index)
        for nested in scene_data.get("shots", []) or []:
            nested = {**nested, "sceneKey": nested.get("sceneKey") or scene["sceneKey"]}
            flat_shots.append(nested)
        scene["shots"] = []
        scenes.append(scene)

    if not scenes and flat_shots:
        for scene_key in _unique([shot.get("sceneKey") or "Scene 1" for shot in flat_shots]):
            scenes.append(_normalize_scene({"sceneKey": scene_key, "title": scene_key}, len(scenes) + 1))

    target_generation = {
        "primary": "ComfyUI with LTX 2.3",
        "model": "LTX 2.3 image-to-video",
        "alternates": ["Veo", "Kling"],
        "minimumResolution": "1080p",
        "aspectRatio": "16:9",
        "delivery": "Organize outputs into bins by scene number and return best takes plus notes.",
    }
    target_generation.update(args.get("target_generation") or {})

    manifest = {
        "schema": "master-canvas-handoff-v1",
        "title": args.get("title") or "Untitled Master Canvas Project",
        "projectId": args.get("project_id") or f"mc-{uuid.uuid4().hex[:12]}",
        "exportedAt": _now(),
        "intent": args.get("brief") or "Master Canvas package generated autonomously by Hermes Agent.",
        "targetGeneration": target_generation,
        "continuity": args.get("continuity") or {},
        "scenes": scenes,
        "shots": [],
        "workflows": [],
        "references": args.get("references") or [],
        "assets": [],
    }
    for shot_data in flat_shots:
        shot = _normalize_shot(shot_data, len(manifest["shots"]) + 1)
        _ensure_scene(manifest, shot["sceneKey"])
        _upsert_shot_in_manifest(manifest, shot)
    _resequence_manifest(manifest)
    return manifest


def _normalize_scene(scene, index):
    scene_key = scene.get("sceneKey") or scene.get("scene") or f"Scene {index}"
    return {
        "sceneKey": scene_key,
        "sceneNumber": scene.get("sceneNumber") or str(index),
        "title": scene.get("title") or scene_key,
        "orderLabel": scene.get("orderLabel") or scene_key,
        "description": scene.get("description") or scene.get("overallPrompt") or "",
        "stylePrompt": scene.get("stylePrompt") or "",
        "musicPrompt": scene.get("musicPrompt") or "",
        "notes": scene.get("notes") or "",
        "shots": list(scene.get("shots") or []),
    }


def _normalize_shot(shot, index):
    scene_key = shot.get("sceneKey") or shot.get("scene") or "Scene 1"
    order_label = shot.get("orderLabel") or f"{scene_key.replace(' ', '')}-{index:02d}"
    return {
        "id": shot.get("id") or f"shot-{uuid.uuid4().hex[:10]}",
        "nodeId": shot.get("nodeId") or shot.get("id") or f"node-{uuid.uuid4().hex[:10]}",
        "assetId": shot.get("assetId") or "",
        "assetName": shot.get("assetName") or "",
        "assetPath": shot.get("assetPath") or "",
        "sceneKey": scene_key,
        "sceneNumber": shot.get("sceneNumber") or "",
        "shotNumber": int(shot.get("shotNumber") or index),
        "orderLabel": order_label,
        "beatTitle": shot.get("beatTitle") or shot.get("title") or order_label,
        "title": shot.get("title") or shot.get("beatTitle") or order_label,
        "status": shot.get("status") or "ready",
        "prompt": shot.get("prompt") or "",
        "negativePrompt": shot.get("negativePrompt") or "",
        "notes": shot.get("notes") or "",
        "tags": shot.get("tags") or "",
        "shotSize": shot.get("shotSize") or "",
        "cameraAngle": shot.get("cameraAngle") or "",
        "cameraMovement": shot.get("cameraMovement") or "",
        "subjectAction": shot.get("subjectAction") or "",
        "location": shot.get("location") or "",
        "mood": shot.get("mood") or "",
        "lighting": shot.get("lighting") or "",
        "lensFeel": shot.get("lensFeel") or "",
        "provider": shot.get("provider") or "",
        "model": shot.get("model") or "",
        "aspectRatio": shot.get("aspectRatio") or "16:9",
        "resolution": _normalize_resolution(shot.get("resolution") or "1080p"),
        "duration": shot.get("duration") or "4s",
        "seed": shot.get("seed") or "",
        "reviewDecision": shot.get("reviewDecision") or "",
        "reviewNotes": shot.get("reviewNotes") or "",
        "sourcePath": shot.get("sourcePath") or "",
        "outputBin": shot.get("outputBin") or f"renders/{_scene_folder(scene_key)}",
    }


def _copy_assets_for_manifest(package_dir, manifest):
    for scene in manifest.get("scenes", []):
        for shot in scene.get("shots", []):
            _attach_asset_to_shot(package_dir, shot, manifest)


def _attach_asset_to_shot(package_dir, shot, manifest):
    asset_path = shot.pop("assetPath", "") or ""
    if not asset_path:
        return
    source = _resolve(asset_path)
    if not source.exists() or not source.is_file():
        raise ValueError(f"assetPath does not exist or is not a file: {asset_path}")
    scene_folder = _scene_folder(shot["sceneKey"])
    target_dir = package_dir / "assets" / scene_folder
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = f"{_safe_slug(shot.get('orderLabel') or shot.get('title') or source.stem)}-{_safe_slug(source.stem)}{source.suffix}"
    target = target_dir / target_name
    shutil.copy2(source, target)
    shot["sourcePath"] = str(target.relative_to(package_dir))
    asset_id = shot.get("assetId") or f"asset-{uuid.uuid4().hex[:10]}"
    shot["assetId"] = asset_id
    shot["assetName"] = source.name
    if not any(asset.get("id") == asset_id for asset in manifest.setdefault("assets", [])):
        mime, _encoding = mimetypes.guess_type(str(source))
        manifest["assets"].append(
            {
                "id": asset_id,
                "name": source.name,
                "type": _asset_type(mime, source.suffix),
                "mime": mime or "",
                "size": source.stat().st_size,
                "tags": shot.get("tags", ""),
                "notes": shot.get("notes", ""),
                "externalUrl": "",
                "sourcePath": shot["sourcePath"],
            }
        )


def _write_package_files(package_dir, manifest):
    _resequence_manifest(manifest)
    _write_text(package_dir / "README.md", _root_readme(manifest))
    _write_json(package_dir / "project_manifest.json", manifest)
    _write_text(package_dir / "timeline" / "shot_order.csv", _shot_order_csv(manifest))
    _write_json(package_dir / "timeline" / "scene_bins.json", _scene_bins(manifest))
    _write_text(package_dir / "hermes-agent" / "README_FOR_HERMES.md", _hermes_readme(manifest))
    _write_json(package_dir / "hermes-agent" / "hermes_job.json", _hermes_job(manifest))
    _write_text(package_dir / "hermes-agent" / "shot_order.csv", _shot_order_csv(manifest))
    _write_text(package_dir / "hermes-agent" / "asset_inventory.csv", _asset_inventory_csv(manifest))
    _write_text(package_dir / "comfyui" / "README_COMFYUI_LTX23.md", _comfy_readme(manifest))
    _write_json(package_dir / "comfyui" / "shot_manifest_ltx23.json", _comfy_manifest(manifest))
    _write_json(package_dir / "comfyui" / "workflow_templates" / "ltx23_adapter_template.json", _comfy_adapter_template())
    for shot in manifest.get("shots", []):
        _write_json(
            package_dir / "comfyui" / "jobs" / _scene_folder(shot["sceneKey"]) / f"{shot['orderLabel']}.json",
            _comfy_shot_job(shot, manifest),
        )
        prompt_dir = package_dir / "kling-veo" / "prompts" / _scene_folder(shot["sceneKey"])
        _write_text(prompt_dir / f"{shot['orderLabel']}_prompt.txt", _operator_prompt_text(shot))
        _write_text(prompt_dir / f"{shot['orderLabel']}_negative.txt", shot.get("negativePrompt", ""))
    _write_text(package_dir / "kling-veo" / "README_KLING_VEO.md", _kling_veo_readme(manifest))
    _write_text(package_dir / "kling-veo" / "shot_checklist.csv", _shot_order_csv(manifest))
    _write_json(package_dir / "deliverables" / "bin_plan.json", _deliverable_bin_plan(manifest))


def _write_json(path, data):
    _write_text(path, json.dumps(data, indent=2))


def _write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_zip(package_dir, zip_path=None, overwrite=False):
    zip_path = Path(zip_path) if zip_path else package_dir.with_suffix(".zip")
    if zip_path.exists() and overwrite:
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(package_dir.rglob("*")):
            if file_path.is_file():
                archive.write(file_path, file_path.relative_to(package_dir))
    return zip_path


def _upsert_shot_in_manifest(manifest, shot):
    shots = manifest.setdefault("shots", [])
    match = _find_shot_index(shots, shot)
    if match >= 0:
        shots[match].update(shot)
        shot = shots[match]
    else:
        shots.append(shot)
    scene = _ensure_scene(manifest, shot["sceneKey"])
    scene_shots = scene.setdefault("shots", [])
    scene_match = _find_shot_index(scene_shots, shot)
    if scene_match >= 0:
        scene_shots[scene_match].update(shot)
    else:
        scene_shots.append(dict(shot))


def _ensure_scene(manifest, scene_key):
    scenes = manifest.setdefault("scenes", [])
    index = _find_scene_index(scenes, scene_key)
    if index >= 0:
        return scenes[index]
    scene = _normalize_scene({"sceneKey": scene_key, "title": scene_key}, len(scenes) + 1)
    scenes.append(scene)
    return scene


def _find_scene_index(scenes, scene_key):
    for index, scene in enumerate(scenes):
        if scene.get("sceneKey") == scene_key:
            return index
    return -1


def _find_shot_index(shots, shot):
    for index, candidate in enumerate(shots):
        if shot.get("id") and candidate.get("id") == shot.get("id"):
            return index
        if candidate.get("sceneKey") == shot.get("sceneKey") and candidate.get("orderLabel") == shot.get("orderLabel"):
            return index
    return -1


def _resequence_manifest(manifest):
    manifest["exportedAt"] = _now()
    flat = []
    for scene_index, scene in enumerate(manifest.get("scenes", []), start=1):
        scene["sceneNumber"] = scene.get("sceneNumber") or str(scene_index)
        shots = scene.get("shots", [])
        for shot_index, shot in enumerate(shots, start=1):
            shot["sceneNumber"] = scene["sceneNumber"]
            shot["shotNumber"] = shot_index
            shot["outputBin"] = shot.get("outputBin") or f"renders/{_scene_folder(scene['sceneKey'])}"
            flat.append(shot)
    for global_index, shot in enumerate(flat, start=1):
        shot["globalOrder"] = global_index
        shot["globalOrderLabel"] = f"{global_index:02d}"
    manifest["shots"] = [dict(shot) for shot in flat]


def _root_readme(manifest):
    return f"""# {manifest.get('title')} - Master Canvas Handoff

Exported: {manifest.get('exportedAt')}

This package was created for Master Canvas and Hermes Agent.

- `project_manifest.json`: structured source of truth
- `assets/`: copied source assets when provided
- `timeline/shot_order.csv`: scene and shot order
- `hermes-agent/`: Hermes task brief and JSON job packet
- `comfyui/`: LTX/ComfyUI shot manifest and per-shot jobs
- `kling-veo/`: prompt sheets for hosted generation tools
- `deliverables/bin_plan.json`: target output bins

Important rule: preserve scene order, shot order, source assets, prompts, negative prompts, continuity, and output bins.
"""


def _hermes_readme(manifest):
    return f"""# Hermes Agent Brief

Project: {manifest.get('title')}

Goal:
{manifest.get('intent', '')}

Use `../project_manifest.json` as the source of truth. Generate or hand off every shot in exact order and organize outputs by scene bin.
"""


def _comfy_readme(manifest):
    model = manifest.get("targetGeneration", {}).get("model", "LTX 2.3 image-to-video")
    return f"""# ComfyUI / {model} Handoff

Use `shot_manifest_ltx23.json` for the batch plan and `jobs/` for per-shot adapter jobs.

Map each job into the installed local graph:
- sourceImage -> image/reference frame input
- prompt -> positive prompt
- negativePrompt -> negative prompt
- settings.resolution -> width/height
- settings.duration -> frame count or seconds
- outputName/outputBin -> save path
"""


def _kling_veo_readme(manifest):
    return f"""# Kling / Veo Operator Handoff

Project: {manifest.get('title')}

Use `shot_checklist.csv` for the order and `prompts/` for per-shot prompt and negative prompt files.
"""


def _hermes_job(manifest):
    return {
        "agent": "Hermes",
        "source": "Master Canvas handoff package",
        "task": "Generate or hand off all shots and return organized scene bins.",
        "qualityFloor": manifest.get("targetGeneration", {}).get("minimumResolution", "1080p"),
        "primaryEngine": manifest.get("targetGeneration", {}).get("primary", "ComfyUI with LTX 2.3"),
        "continuity": manifest.get("continuity", {}),
        "inputs": {
            "projectManifest": "../project_manifest.json",
            "comfyManifest": "../comfyui/shot_manifest_ltx23.json",
            "shotOrderCsv": "shot_order.csv",
            "assetInventoryCsv": "asset_inventory.csv",
        },
        "requiredOutputBins": _deliverable_bin_plan(manifest),
        "shots": manifest.get("shots", []),
    }


def _comfy_manifest(manifest):
    return {
        "engine": "ComfyUI",
        "model": manifest.get("targetGeneration", {}).get("model", "LTX 2.3 image-to-video"),
        "resolution": "1920x1080",
        "aspectRatio": "16:9",
        "scenes": [
            {
                "sceneKey": scene.get("sceneKey"),
                "sceneNumber": scene.get("sceneNumber"),
                "outputBin": f"renders/{_scene_folder(scene.get('sceneKey', 'scene'))}",
                "description": scene.get("description", ""),
                "stylePrompt": scene.get("stylePrompt", ""),
                "musicPrompt": scene.get("musicPrompt", ""),
                "shots": [_comfy_shot_job(shot, manifest) for shot in scene.get("shots", [])],
            }
            for scene in manifest.get("scenes", [])
        ],
    }


def _comfy_shot_job(shot, manifest):
    return {
        "engine": "ComfyUI",
        "model": manifest.get("targetGeneration", {}).get("model", "LTX 2.3 image-to-video"),
        "projectTitle": manifest.get("title"),
        "sceneKey": shot.get("sceneKey"),
        "sceneNumber": shot.get("sceneNumber"),
        "shotNumber": shot.get("shotNumber"),
        "orderLabel": shot.get("orderLabel"),
        "sourceImage": shot.get("sourcePath", ""),
        "outputBin": shot.get("outputBin"),
        "outputName": f"{shot.get('orderLabel')}-{_safe_slug(shot.get('beatTitle') or shot.get('title') or 'shot')}",
        "settings": {
            "aspectRatio": shot.get("aspectRatio", "16:9"),
            "resolution": _normalize_resolution(shot.get("resolution", "1080p")),
            "duration": shot.get("duration", "4s"),
            "seed": shot.get("seed") or "auto",
            "fps": 24,
            "qualityTarget": "1080p minimum, prefer higher if stable",
        },
        "prompt": shot.get("prompt", ""),
        "negativePrompt": shot.get("negativePrompt", ""),
        "camera": {
            "shotSize": shot.get("shotSize", ""),
            "angle": shot.get("cameraAngle", ""),
            "movement": shot.get("cameraMovement", ""),
            "lens": shot.get("lensFeel", ""),
            "lighting": shot.get("lighting", ""),
            "action": shot.get("subjectAction", ""),
        },
        "continuity": manifest.get("continuity", {}),
        "notes": shot.get("notes", ""),
    }


def _comfy_adapter_template():
    return {
        "name": "LTX image-to-video adapter template",
        "purpose": "Map each comfyui/jobs/* shot JSON into the installed local LTX graph.",
        "requiredInputs": {
            "sourceImage": "LoadImage or equivalent first-frame/reference-image input",
            "prompt": "Positive prompt text node",
            "negativePrompt": "Negative prompt text node",
            "resolution": "Width/height or preset node, 1920x1080 recommended",
            "duration": "Frame count or seconds field depending on local LTX node",
            "seed": "Seed field, auto allowed unless retrying",
            "outputName": "SaveVideo/SaveImage filename prefix",
            "outputBin": "Output folder/bin target",
        },
    }


def _scene_bins(manifest):
    return [
        {
            "sceneKey": scene.get("sceneKey"),
            "sceneNumber": scene.get("sceneNumber"),
            "outputBin": f"renders/{_scene_folder(scene.get('sceneKey', 'scene'))}",
            "shotCount": len(scene.get("shots", [])),
        }
        for scene in manifest.get("scenes", [])
    ]


def _deliverable_bin_plan(manifest):
    return {
        "root": "renders",
        "bins": _scene_bins(manifest),
        "return": ["best_takes", "alternate_takes", "settings_and_seeds", "operator_notes"],
    }


def _shot_order_csv(manifest):
    handle = StringIO()
    writer = csv.DictWriter(
        handle,
        fieldnames=["globalOrder", "sceneKey", "shotNumber", "orderLabel", "title", "sourcePath", "duration", "resolution", "outputBin"],
    )
    writer.writeheader()
    for shot in manifest.get("shots", []):
        writer.writerow({field: shot.get(field, "") for field in writer.fieldnames})
    return handle.getvalue()


def _asset_inventory_csv(manifest):
    handle = StringIO()
    writer = csv.DictWriter(handle, fieldnames=["id", "name", "type", "mime", "size", "sourcePath", "tags", "notes", "externalUrl"])
    writer.writeheader()
    for asset in manifest.get("assets", []):
        writer.writerow({field: asset.get(field, "") for field in writer.fieldnames})
    return handle.getvalue()


def _operator_prompt_text(shot):
    lines = [
        f"Shot: {shot.get('orderLabel')} - {shot.get('title')}",
        f"Scene: {shot.get('sceneKey')}",
        f"Source asset: {shot.get('sourcePath', '')}",
        "",
        "Prompt:",
        shot.get("prompt", ""),
        "",
        "Camera / Lens / Lighting / Action:",
        f"Lens: {shot.get('lensFeel', '')}",
        f"Lighting: {shot.get('lighting', '')}",
        f"Movement: {shot.get('cameraMovement', '')}",
        f"Action: {shot.get('subjectAction', '')}",
        "",
        "Notes:",
        shot.get("notes", ""),
    ]
    return "\n".join(lines)


def _unique(values):
    seen = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def _asset_type(mime, suffix):
    mime = mime or ""
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("audio/"):
        return "audio"
    if suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
        return "image"
    return "file"


def _normalize_resolution(value):
    if value == "1080p":
        return "1920x1080"
    if value == "4k":
        return "3840x2160"
    return value


def _scene_folder(scene_key: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in scene_key).strip("-")
    return cleaned or "scene"


def _safe_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in str(value)).strip("-")
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned[:80] or "item"


def _now():
    return datetime.now(timezone.utc).isoformat()
