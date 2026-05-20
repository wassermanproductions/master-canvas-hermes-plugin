"""Tool schemas exposed to Hermes for Master Canvas packages."""

PACKAGE_PATH_FIELD = {
    "type": "string",
    "description": "Absolute or user-relative path to a Master Canvas handoff ZIP, extracted package folder, or project_manifest.json.",
}


MASTERCANVAS_CAPABILITIES = {
    "name": "mastercanvas_capabilities",
    "description": "Explain how to use the Master Canvas Hermes plugin and handoff package structure.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}


SCENE_FIELD = {
    "type": "object",
    "description": "A scene to create in the Master Canvas package.",
    "properties": {
        "sceneKey": {"type": "string", "description": "Stable scene key such as Scene 1."},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "stylePrompt": {"type": "string"},
        "musicPrompt": {"type": "string"},
        "notes": {"type": "string"},
        "shots": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}


SHOT_FIELD = {
    "type": "object",
    "description": "A shot to create or update. Use sceneKey and orderLabel to preserve order.",
    "properties": {
        "sceneKey": {"type": "string"},
        "orderLabel": {"type": "string"},
        "title": {"type": "string"},
        "beatTitle": {"type": "string"},
        "prompt": {"type": "string"},
        "negativePrompt": {"type": "string"},
        "assetPath": {"type": "string", "description": "Optional local source image/video/audio path to copy into the package."},
        "sourcePath": {"type": "string", "description": "Optional existing package-relative source path."},
        "duration": {"type": "string"},
        "resolution": {"type": "string"},
        "aspectRatio": {"type": "string"},
        "cameraMovement": {"type": "string"},
        "lensFeel": {"type": "string"},
        "lighting": {"type": "string"},
        "subjectAction": {"type": "string"},
        "notes": {"type": "string"},
        "tags": {"type": "string"},
    },
    "additionalProperties": True,
}


MASTERCANVAS_CREATE_PACKAGE = {
    "name": "mastercanvas_create_package",
    "description": "Create a Master Canvas handoff package folder from a project brief, scenes, shots, optional asset paths, references, continuity, and target generation settings.",
    "parameters": {
        "type": "object",
        "properties": {
            "output_dir": {
                "type": "string",
                "description": "Folder where the Master Canvas handoff package should be created.",
            },
            "title": {"type": "string"},
            "brief": {"type": "string", "description": "Overall project goal or creative brief."},
            "scenes": {"type": "array", "items": SCENE_FIELD},
            "shots": {
                "type": "array",
                "description": "Optional flat shot list. Shots nested inside scenes are also accepted.",
                "items": SHOT_FIELD,
            },
            "references": {"type": "array", "items": {"type": "object"}, "default": []},
            "continuity": {"type": "object", "default": {}},
            "target_generation": {"type": "object", "default": {}},
            "overwrite": {"type": "boolean", "default": False},
            "zip": {"type": "boolean", "description": "Also create a ZIP next to output_dir.", "default": False},
        },
        "required": ["output_dir", "title"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_UPSERT_SCENE = {
    "name": "mastercanvas_upsert_scene",
    "description": "Add or update one scene in an extracted Master Canvas package folder or project_manifest.json.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
            "scene": SCENE_FIELD,
        },
        "required": ["package_path", "scene"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_UPSERT_SHOT = {
    "name": "mastercanvas_upsert_shot",
    "description": "Add or update one shot in an extracted Master Canvas package folder or project_manifest.json, optionally copying a local asset into the package.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
            "shot": SHOT_FIELD,
        },
        "required": ["package_path", "shot"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_PACKAGE_ZIP = {
    "name": "mastercanvas_package_zip",
    "description": "Create a ZIP file from an extracted Master Canvas handoff package folder.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
            "zip_path": {"type": "string", "description": "Output ZIP path. Defaults to package folder name plus .zip."},
            "overwrite": {"type": "boolean", "default": False},
        },
        "required": ["package_path"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_INSPECT_PACKAGE = {
    "name": "mastercanvas_inspect_package",
    "description": "Read a Master Canvas handoff ZIP or manifest and summarize project, scenes, shots, assets, references, target generation settings, and readiness.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
        },
        "required": ["package_path"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_EXTRACT_PACKAGE = {
    "name": "mastercanvas_extract_package",
    "description": "Extract a Master Canvas handoff ZIP into a local folder for ComfyUI, LTX, Kling, Veo, or operator handoff.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
            "output_dir": {
                "type": "string",
                "description": "Absolute or user-relative folder where the package should be extracted.",
            },
            "overwrite": {
                "type": "boolean",
                "description": "When false, refuse to overwrite existing files.",
                "default": False,
            },
        },
        "required": ["package_path", "output_dir"],
        "additionalProperties": False,
    },
}


MASTERCANVAS_COMFY_PLAN = {
    "name": "mastercanvas_comfy_plan",
    "description": "Build a shot-by-shot ComfyUI/LTX execution plan from a Master Canvas package or manifest.",
    "parameters": {
        "type": "object",
        "properties": {
            "package_path": PACKAGE_PATH_FIELD,
        },
        "required": ["package_path"],
        "additionalProperties": False,
    },
}
