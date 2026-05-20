import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import tools
import __init__ as plugin


class FakeContext:
    def __init__(self):
        self.tools = []
        self.skills = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_skill(self, name, path):
        self.skills.append((name, Path(path)))


class MasterCanvasPluginTest(unittest.TestCase):
    def test_registers_tools_and_skill(self):
        ctx = FakeContext()
        plugin.register(ctx)
        self.assertEqual(
            {item["name"] for item in ctx.tools},
            {
                "mastercanvas_capabilities",
                "mastercanvas_create_package",
                "mastercanvas_upsert_scene",
                "mastercanvas_upsert_shot",
                "mastercanvas_package_zip",
                "mastercanvas_inspect_package",
                "mastercanvas_extract_package",
                "mastercanvas_comfy_plan",
            },
        )
        self.assertEqual(ctx.skills, [("handoff", ROOT / "skills" / "handoff")])

    def test_capabilities_returns_json_string(self):
        payload = json.loads(tools.handle_capabilities({}))
        self.assertTrue(payload["success"])
        self.assertEqual(payload["toolset"], "mastercanvas")

    def test_manifest_inspection_and_plan(self):
        manifest = {
            "title": "Demo",
            "schema": "master-canvas-handoff/v1",
            "targetGeneration": {"model": "LTX 2.3", "minimumResolution": "1080p"},
            "assets": [{"id": "asset-1"}],
            "references": [],
            "scenes": [{"sceneKey": "Scene 1", "shots": [{"id": "shot-1"}]}],
            "shots": [
                {
                    "orderLabel": "S1-01",
                    "sceneKey": "Scene 1",
                    "title": "Opening Shot",
                    "sourcePath": "assets/scene-1/opening.png",
                    "outputBin": "renders/scene-1",
                    "duration": "4s",
                    "resolution": "1920x1080",
                    "prompt": "Move slowly through the opening image.",
                    "negativePrompt": "No identity drift.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "project_manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            inspected = json.loads(tools.handle_inspect_package({"package_path": str(manifest_path)}))
            self.assertTrue(inspected["ready"])
            self.assertEqual(inspected["shot_count"], 1)

            plan = json.loads(tools.handle_comfy_plan({"package_path": str(manifest_path)}))
            self.assertEqual(plan["model"], "LTX 2.3")
            self.assertEqual(plan["shots"][0]["orderLabel"], "S1-01")

    def test_autonomous_create_update_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            asset = tmp_path / "frame.jpg"
            asset.write_bytes(b"fake-jpeg")
            package_dir = tmp_path / "autonomous-package"

            created = json.loads(
                tools.handle_create_package(
                    {
                        "output_dir": str(package_dir),
                        "title": "Autonomous Demo",
                        "brief": "Create a demo directly from Hermes.",
                        "scenes": [
                            {
                                "sceneKey": "Scene 1",
                                "title": "Opening",
                                "description": "A clean opening beat.",
                                "shots": [
                                    {
                                        "orderLabel": "S1-01",
                                        "title": "First Frame",
                                        "prompt": "Animate the opening frame.",
                                        "negativePrompt": "No artifacts.",
                                        "assetPath": str(asset),
                                    }
                                ],
                            }
                        ],
                    }
                )
            )
            self.assertTrue(created["success"])
            self.assertTrue((package_dir / "project_manifest.json").exists())
            self.assertTrue((package_dir / "comfyui" / "jobs" / "scene-1" / "S1-01.json").exists())

            manifest = json.loads((package_dir / "project_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["shots"][0]["sourcePath"], "assets/scene-1/s1-01-frame.jpg")

            updated = json.loads(
                tools.handle_upsert_shot(
                    {
                        "package_path": str(package_dir),
                        "shot": {
                            "sceneKey": "Scene 1",
                            "orderLabel": "S1-02",
                            "title": "Second Shot",
                            "prompt": "Continue the motion.",
                            "negativePrompt": "No flicker.",
                        },
                    }
                )
            )
            self.assertTrue(updated["success"])

            zipped = json.loads(tools.handle_package_zip({"package_path": str(package_dir), "overwrite": True}))
            self.assertTrue(zipped["success"])
            self.assertTrue(Path(zipped["zip_path"]).exists())


if __name__ == "__main__":
    unittest.main()
