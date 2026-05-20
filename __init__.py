"""Hermes plugin registration for Master Canvas handoff tools and skills."""

from __future__ import annotations

from pathlib import Path

try:
    from . import schemas
    from .tools import (
        handle_capabilities,
        handle_comfy_plan,
        handle_create_package,
        handle_extract_package,
        handle_inspect_package,
        handle_package_zip,
        handle_upsert_scene,
        handle_upsert_shot,
    )
except ImportError:
    import schemas
    from tools import (
        handle_capabilities,
        handle_comfy_plan,
        handle_create_package,
        handle_extract_package,
        handle_inspect_package,
        handle_package_zip,
        handle_upsert_scene,
        handle_upsert_shot,
    )


TOOLS = [
    (
        "mastercanvas_capabilities",
        schemas.MASTERCANVAS_CAPABILITIES,
        handle_capabilities,
        "Explain how to use Master Canvas handoff packages.",
    ),
    (
        "mastercanvas_create_package",
        schemas.MASTERCANVAS_CREATE_PACKAGE,
        handle_create_package,
        "Create a Master Canvas handoff package from a brief, scenes, shots, and assets.",
    ),
    (
        "mastercanvas_upsert_scene",
        schemas.MASTERCANVAS_UPSERT_SCENE,
        handle_upsert_scene,
        "Add or update a scene in a Master Canvas handoff manifest.",
    ),
    (
        "mastercanvas_upsert_shot",
        schemas.MASTERCANVAS_UPSERT_SHOT,
        handle_upsert_shot,
        "Add or update a shot in a Master Canvas handoff manifest.",
    ),
    (
        "mastercanvas_package_zip",
        schemas.MASTERCANVAS_PACKAGE_ZIP,
        handle_package_zip,
        "Package an extracted Master Canvas handoff folder as a ZIP.",
    ),
    (
        "mastercanvas_inspect_package",
        schemas.MASTERCANVAS_INSPECT_PACKAGE,
        handle_inspect_package,
        "Inspect a Master Canvas package and summarize generation readiness.",
    ),
    (
        "mastercanvas_extract_package",
        schemas.MASTERCANVAS_EXTRACT_PACKAGE,
        handle_extract_package,
        "Extract a Master Canvas handoff ZIP to a local folder.",
    ),
    (
        "mastercanvas_comfy_plan",
        schemas.MASTERCANVAS_COMFY_PLAN,
        handle_comfy_plan,
        "Create a concise ComfyUI/LTX execution plan from a Master Canvas package.",
    ),
]


def register(ctx):
    """Register tools and the bundled handoff skill with Hermes."""
    for name, schema, handler, description in TOOLS:
        ctx.register_tool(
            name=name,
            toolset="mastercanvas",
            schema=schema,
            handler=handler,
            description=description,
        )

    skill_path = Path(__file__).parent / "skills" / "handoff"
    if skill_path.exists():
        ctx.register_skill("handoff", skill_path)
