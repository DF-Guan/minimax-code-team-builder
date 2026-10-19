"""Push locally generated agent avatars to the account roster (the web / cloud side).

Why this exists
---------------
A custom agent's avatar is a *local file* in its agent directory, and the account keeps
its own avatar record for the same agent. The local runtime never pushes either one —
its agent module makes no cloud calls at all. So a team built locally shows its
generated icons in the desktop app, while the account copy falls back to the default
letter avatar until someone sets it.

The account agent API accepts an `avatar_object_key` instead of a URL, which is what
makes this possible. The chain, verified against the installed client bundle:

  1. POST {cloud}/minimax-cloud/api/v1/uploads/prepare
         {purpose: 5 (AgentAvatar), file_name, mime_type, size_bytes}
         -> {object_key, upload_instruction: {url, form_fields, method}}
  2. POST multipart to upload_instruction.url            -> 204
  3. PATCH {cloud}/minimax-cloud/api/v1/agent
         {name: <account agent id>, avatar_object_key: <object_key>}

Authentication reuses the client's own signed-in token, so this only ever touches the
signed-in account. The account agent id is matched to the local agent by
`display_name`, because the account side stores a numeric id rather than a slug.

Usage:
    python push_cloud_avatars.py --dry-run          # plan only
    python push_cloud_avatars.py --only <slug>      # one agent
    python push_cloud_avatars.py                    # all local agents

Caveat: the cloud routes above are an internal contract, not a published API. If they
change, this script stops working — the local avatars are unaffected either way.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
import urllib.error
import urllib.request
import uuid

CLOUD_BASE = "https://agent.minimax.cn/minimax-cloud/api/v1"
PURPOSE_AGENT_AVATAR = 5
AVATAR_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def resolve_data_dir(explicit: str | None) -> str:
    if explicit:
        return os.path.abspath(explicit)
    for name in ("MINIMAX_DATA_DIR", "MAVIS_DATA_DIR", "__MAVIS_RUNTIME_DATA_DIR"):
        value = os.environ.get(name)
        if value:
            return os.path.abspath(value)
    if platform.system() == "Windows":
        raise SystemExit(
            "No data directory given. Pass --data-dir, or set MINIMAX_DATA_DIR.\n"
            "It is the folder that contains the 'agents' directory."
        )
    return os.path.abspath(os.path.join(os.path.expanduser("~"), ".minimax"))


def auth_candidates(data_dir: str):
    root = os.path.join(data_dir, "auth")
    for dirpath, _dirnames, filenames in os.walk(root):
        if "auth.json" in filenames:
            yield os.path.join(dirpath, "auth.json")


def access_token(data_dir: str) -> str:
    now = int(time.time() * 1000)
    for path in auth_candidates(data_dir):
        try:
            store = json.load(open(path, encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = [
            r for r in store.get("records", {}).values()
            if r.get("accessToken") and r.get("expiresAtMs", 0) > now
        ]
        if records:
            records.sort(key=lambda r: -r["expiresAtMs"])
            return records[0]["accessToken"]
    raise SystemExit(
        "no valid access token found in the runtime auth store.\n"
        "Sign in through the app and make a request so it refreshes, then re-run."
    )


def call(token: str, url: str, method: str = "GET", payload=None):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.status, json.loads(response.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")


def roster(token: str):
    status, body = call(token, CLOUD_BASE + "/agent?limit=200")
    if status != 200:
        raise SystemExit(f"roster fetch failed HTTP {status}: {str(body)[:300]}")
    if isinstance(body, str):
        raise SystemExit(f"roster fetch failed: {body[:300]}")
    return body.get("agents") or body.get("data", {}).get("agents") or []


def upload_avatar(token: str, path: str) -> str:
    size = os.path.getsize(path)
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    status, body = call(token, CLOUD_BASE + "/uploads/prepare", "POST", {
        "purpose": PURPOSE_AGENT_AVATAR,
        "file_name": "agent-avatar" + os.path.splitext(path)[1],
        "mime_type": mime,
        "size_bytes": size,
    })
    if status != 200:
        raise RuntimeError(f"prepare failed HTTP {status}: {str(body)[:200]}")
    payload = body.get("data") or body
    key = payload.get("object_key") or payload.get("data")
    instruction = payload.get("upload_instruction") or (payload.get("data") or {}).get("upload_instruction") or {}
    url = instruction.get("url")
    fields = instruction.get("form_fields") or {}
    if not key or not url:
        raise RuntimeError(f"unexpected prepare response: {json.dumps(body)[:300]}")

    boundary = uuid.uuid4().hex
    parts = []
    for name, value in fields.items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode()
        )
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{os.path.basename(path)}\"\r\nContent-Type: {mime}\r\n\r\n".encode()
    )
    with open(path, "rb") as handle:
        parts.append(handle.read())
    parts.append(f"\r\n--{boundary}--\r\n".encode())

    request = urllib.request.Request(
        url, data=b"".join(parts),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        if response.status != 204:
            raise RuntimeError(f"upload failed HTTP {response.status}")
    return key


def read_display_name(agent_md: str):
    for line in open(agent_md, encoding="utf-8"):
        stripped = line.strip()
        if stripped.startswith("displayName:"):
            return stripped.split(":", 1)[1].strip().strip('"')
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=None)
    parser.add_argument("--only", default=None, help="slug of a single agent")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    agents_dir = os.path.join(data_dir, "agents")
    token = access_token(data_dir)

    cloud = roster(token)
    by_display: dict[str, dict] = {}
    for agent in cloud:
        name = (agent.get("display_name") or "").strip()
        if name:
            by_display.setdefault(name, agent)

    local = []
    for slug in sorted(os.listdir(agents_dir)):
        agent_dir = os.path.join(agents_dir, slug)
        agent_md = os.path.join(agent_dir, "agent.md")
        if slug == ".builtin" or not os.path.isfile(agent_md):
            continue
        if args.only and slug != args.only:
            continue
        avatar = next(
            (os.path.join(agent_dir, "avatar" + ext) for ext in AVATAR_EXTENSIONS
             if os.path.isfile(os.path.join(agent_dir, "avatar" + ext))),
            None,
        )
        display = read_display_name(agent_md)
        if display:
            local.append((slug, display, avatar))

    print(f"account roster: {len(cloud)} agents; local candidates: {len(local)}\n")
    updated = skipped = 0
    failed = []
    for slug, display, avatar in local:
        target = by_display.get(display)
        if not target:
            print(f"  SKIP  {slug}: no account agent named {display!r}")
            skipped += 1
            continue
        if not avatar:
            print(f"  SKIP  {slug}: no local avatar file")
            skipped += 1
            continue
        if args.dry_run:
            print(f"  PLAN  {slug} -> account id {target.get('name')} "
                  f"(current avatar: {target.get('avatar') or 'none'})")
            continue
        try:
            key = upload_avatar(token, avatar)
            status, body = call(token, CLOUD_BASE + "/agent", "PATCH",
                                {"name": target["name"], "avatar_object_key": key})
            if status != 200:
                raise RuntimeError(f"patch HTTP {status}: {str(body)[:200]}")
            print(f"  OK    {slug} -> account id {target['name']}")
            updated += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL  {slug}: {exc}")
            failed.append(slug)

    print(f"\nupdated: {updated}   skipped: {skipped}   failed: {len(failed)}")
    if not args.dry_run:
        print("\n=== account roster after ===")
        wanted = {d for _, d, _ in local}
        for agent in roster(token):
            name = (agent.get("display_name") or "").strip()
            if name in wanted:
                print(f"  {name:<50} avatar={'set' if agent.get('avatar') else 'NONE'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
