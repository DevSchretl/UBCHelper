"""Create and configure the Hugging Face Space in one step.

Reads the keys from `.env` and sets them as Space secrets over the API, so live credentials
never pass through a shell command line (and therefore never land in PSReadLine history).
Idempotent: safe to re-run to update settings on an existing Space.

    python scripts/setup_space.py --space DevSchretl/ubc-calendar-rag

The Space runs on `cpu-basic` hardware, which is the default here. ZeroGPU is not an option:
it stops any Space that defines no @spaces.GPU function, and this app needs no GPU (see the
app.py docstring). Afterwards, push the code:

    git remote add hf https://huggingface.co/spaces/<space>
    git push hf main
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import dotenv_values  # noqa: E402

# Copied onto the Space as secrets. HF_TOKEN should be a READ-scoped token: the Space only
# ever pulls the private index dataset, so a write token there adds risk and no capability.
SECRET_KEYS = ("OPENAI_API_KEY", "COHERE_API_KEY", "ANTHROPIC_API_KEY", "HF_TOKEN")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--space", required=True, help="e.g. DevSchretl/ubc-calendar-rag")
    p.add_argument("--env", type=Path, default=Path(".env"))
    p.add_argument("--hardware", default="cpu-basic",
                   help="Space hardware (default: cpu-basic). Not ZeroGPU, which stops a Space "
                        "that has no @spaces.GPU function")
    p.add_argument("--private", action="store_true", help="create it private; flip later in Settings")
    p.add_argument("--per-hour", type=int, default=30, help="DEMO_IP_PER_HOUR (default 30, good for testing)")
    p.add_argument("--per-day", type=int, default=60)
    p.add_argument("--daily-calls", type=int, default=400, help="global DEMO_DAILY_LLM_CALLS ceiling")
    p.add_argument("--salt", default="", help="reuse a specific DEMO_IP_SALT instead of generating one")
    args = p.parse_args()

    env = dotenv_values(args.env)
    missing = [k for k in SECRET_KEYS if not env.get(k)]
    if missing:
        sys.exit(f"{args.env} is missing: {', '.join(missing)}")

    index_repo = env.get("DEMO_INDEX_REPO")
    index_rev = env.get("DEMO_INDEX_REVISION")
    if not index_repo or not index_rev:
        sys.exit("Set DEMO_INDEX_REPO and DEMO_INDEX_REVISION in .env first "
                 "(run scripts/publish_index.py — it prints the sha to pin).")

    from huggingface_hub import HfApi

    api = HfApi()   # the CLI's logged-in WRITE token, for creating and configuring

    # Sanity-check the read token before baking it in, so a bad one fails here rather than as
    # a 401 buried in the Space's startup log.
    try:
        who = HfApi(token=env["HF_TOKEN"]).whoami()
        role = ((who.get("auth") or {}).get("accessToken") or {}).get("role")
        print(f"HF_TOKEN belongs to {who.get('name')} (role: {role})")
        if role not in ("read", "fineGrained"):
            print(f"  note: a '{role}' token is broader than this Space needs; a read token is enough.")
    except Exception as exc:
        sys.exit(f"The HF_TOKEN in {args.env} is not valid: {type(exc).__name__}: {exc}")

    # And that it can actually see the private index — the single most common startup failure.
    try:
        info = HfApi(token=env["HF_TOKEN"]).dataset_info(index_repo)
        if info.sha != index_rev:
            print(f"  warning: DEMO_INDEX_REVISION ({index_rev[:12]}…) is not the dataset HEAD "
                  f"({info.sha[:12]}…). That is fine if you pinned it deliberately.")
    except Exception as exc:
        sys.exit(f"HF_TOKEN cannot read {index_repo}: {type(exc).__name__}: {exc}")

    url = api.create_repo(
        args.space, repo_type="space", space_sdk="gradio",
        space_hardware=args.hardware, private=args.private, exist_ok=True,
    )
    print(f"Space ready: {url}")

    variables = {
        "DEMO_INDEX_REPO": index_repo,
        "DEMO_INDEX_REVISION": index_rev,
        "DEMO_DAILY_LLM_CALLS": str(args.daily_calls),
        "DEMO_IP_PER_HOUR": str(args.per_hour),
        "DEMO_IP_PER_DAY": str(args.per_day),
    }
    for key, value in variables.items():
        api.add_space_variable(args.space, key, value)
        print(f"  variable  {key} = {value}")

    salt = args.salt or env.get("DEMO_IP_SALT") or secrets.token_urlsafe(32)
    for key in SECRET_KEYS:
        api.add_space_secret(args.space, key, env[key])
        print(f"  secret    {key} = {env[key][:6]}… ({len(env[key])} chars)")
    api.add_space_secret(args.space, "DEMO_IP_SALT", salt)
    print(f"  secret    DEMO_IP_SALT = {salt[:6]}… (generated)" if not (args.salt or env.get("DEMO_IP_SALT"))
          else "  secret    DEMO_IP_SALT = (reused)")

    print(f"\nNow push the code:\n"
          f"  git remote add hf https://huggingface.co/spaces/{args.space}\n"
          f"  git push hf main\n"
          f"\nThen watch it start:\n"
          f"  hf spaces logs {args.space}")


if __name__ == "__main__":
    main()
