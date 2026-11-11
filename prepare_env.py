from pathlib import Path
ROOT = Path(__file__).resolve().parent
root_example = ROOT / ".env.server.example"
root_env = ROOT / ".env"
if root_example.exists() and not root_env.exists():
    root_env.write_text(root_example.read_text(encoding="utf-8"), encoding="utf-8")
    print("Created .env")
for name in ("filter", "fit", "nima", "shop"):
    folder = ROOT / "apps" / name
    example = folder / ".env.example"
    target = folder / ".env"
    if example.exists() and not target.exists():
        target.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Created {target.relative_to(ROOT)}")
    elif target.exists():
        print(f"Kept existing {target.relative_to(ROOT)}")
