#!/usr/bin/env python3
import argparse
import os
import sys
from typing import Dict, List, Optional, Tuple

from notion_client import Client


NOTION_VERSION = "2025-09-03"

# Notion property names (must match your DB exactly)
PROP_ALIAS = "Alias"
PROP_USUARIO = "Usuario"
PROP_HOSTNAME = "hostname"
PROP_PUERTO = "puerto"
PROP_CMD = "comando_ssh"


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    sys.exit(code)


def get_client() -> Client:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        die("Missing env var: NOTION_TOKEN")
    return Client(auth=token, notion_version=NOTION_VERSION)


def get_data_source_id(notion: Client, database_id: str) -> str:
    db = notion.databases.retrieve(database_id=database_id)
    ds = db.get("data_sources") or []
    if not ds:
        die("Database has no data_sources. Is DATABASE_ID correct?")
    return ds[0]["id"]


def rich_text_to_plain(rt: Dict) -> str:
    # Notion rich_text array -> plain string
    parts = rt.get("rich_text") or []
    out = []
    for p in parts:
        # Notion uses different keys depending on type
        if "plain_text" in p:
            out.append(p["plain_text"])
        elif p.get("text", {}).get("content"):
            out.append(p["text"]["content"])
    return "".join(out).strip()


def title_to_plain(title_prop: Dict) -> str:
    parts = title_prop.get("title") or []
    out = []
    for p in parts:
        if "plain_text" in p:
            out.append(p["plain_text"])
        elif p.get("text", {}).get("content"):
            out.append(p["text"]["content"])
    return "".join(out).strip()


def page_props(page: Dict) -> Dict:
    return page.get("properties") or {}


def extract_row(page: Dict) -> Tuple[str, str, str, str]:
    props = page_props(page)

    alias = title_to_plain(props.get(PROP_ALIAS, {}))
    usuario = rich_text_to_plain(props.get(PROP_USUARIO, {}))
    hostname = rich_text_to_plain(props.get(PROP_HOSTNAME, {}))
    puerto = rich_text_to_plain(props.get(PROP_PUERTO, {}))

    return alias, usuario, hostname, puerto


def query_all_pages(notion: Client, data_source_id: str) -> List[Dict]:
    results: List[Dict] = []
    cursor = None

    while True:
        payload = {"page_size": 100}
        if cursor:
            payload["start_cursor"] = cursor

        resp = notion.data_sources.query(data_source_id=data_source_id, **payload)
        batch = resp.get("results") or []
        results.extend(batch)

        if resp.get("has_more"):
            cursor = resp.get("next_cursor")
            if not cursor:
                break
        else:
            break

    return results


def cmd_list_ports(notion: Client, database_id: str, fmt: str) -> int:
    ds_id = get_data_source_id(notion, database_id)
    pages = query_all_pages(notion, ds_id)

    rows = []
    for p in pages:
        alias, usuario, hostname, puerto = extract_row(p)
        if puerto:
            rows.append((puerto, alias, usuario, hostname))

    # Sort by numeric port if possible, otherwise string
    def sort_key(r):
        try:
            return (0, int(r[0]), r[1])
        except Exception:
            return (1, r[0], r[1])

    rows.sort(key=sort_key)

    if fmt == "plain":
        for puerto, alias, *_ in rows:
            print(puerto)
    elif fmt == "csv":
        print("puerto,alias,usuario,hostname")
        for puerto, alias, usuario, hostname in rows:
            # very simple CSV escaping (ports/aliases won’t contain commas typically)
            print(f"{puerto},{alias},{usuario},{hostname}")
    else:  # table
        # simple aligned table
        w_port = max([5] + [len(r[0]) for r in rows])
        w_alias = max([5] + [len(r[1]) for r in rows])
        print(f"{'puerto'.ljust(w_port)}  {'alias'.ljust(w_alias)}  usuario  hostname")
        print(f"{'-'*w_port}  {'-'*w_alias}  ------  --------")
        for puerto, alias, usuario, hostname in rows:
            print(f"{puerto.ljust(w_port)}  {alias.ljust(w_alias)}  {usuario}  {hostname}")

    return 0


def port_exists(notion: Client, data_source_id: str, puerto: str) -> bool:
    # Notion filter for rich_text equals on property "puerto"
    resp = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "property": PROP_PUERTO,
            "rich_text": {"equals": puerto},
        },
        page_size=1,
    )
    return bool(resp.get("results"))


def alias_exists(notion: Client, data_source_id: str, alias: str) -> bool:
    resp = notion.data_sources.query(
        data_source_id=data_source_id,
        filter={
            "property": PROP_ALIAS,
            "title": {"equals": alias},
        },
        page_size=1,
    )
    return bool(resp.get("results"))


def cmd_add_row(
    notion: Client,
    database_id: str,
    alias: str,
    usuario: str,
    hostname: str,
    puerto: Optional[str],
    no_check: bool,
) -> int:
    ds_id = get_data_source_id(notion, database_id)

    if not no_check:
        if alias_exists(notion, ds_id, alias):
            die(f"Alias already exists: {alias}", code=10)
        if puerto and port_exists(notion, ds_id, puerto):
            die(f"Port already exists: {puerto}", code=11)

    props = {
        PROP_ALIAS: {"title": [{"text": {"content": alias}}]},
        PROP_USUARIO: {"rich_text": [{"text": {"content": usuario}}]},
        PROP_HOSTNAME: {"rich_text": [{"text": {"content": hostname}}]},
        PROP_CMD: {"rich_text": [{"text": {"content": f"ssh {usuario}@{alias}"}}]},
    }

    if puerto:
        props[PROP_PUERTO] = {"rich_text": [{"text": {"content": puerto}}]}

    notion.pages.create(
        parent={"type": "data_source_id", "data_source_id": ds_id},
        properties=props,
    )

    print(f"Created: {alias}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Notion SSH/FRP DB helper (list ports, add row)."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list-ports", help="List all existing ports from Notion")
    p_list.add_argument(
        "--format", choices=["plain", "csv", "table"], default="plain",
        help="Output format"
    )

    p_add = sub.add_parser("add-row", help="Insert a new row into Notion")
    p_add.add_argument("--alias", required=True)
    p_add.add_argument("--usuario", required=True)
    p_add.add_argument("--hostname", required=True)
    p_add.add_argument("--puerto", default="", help="Port (optional)")
    p_add.add_argument(
        "--no-check", action="store_true",
        help="Skip duplicate checks (alias/puerto)."
    )

    args = parser.parse_args()

    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not db_id:
        die("Missing env var: NOTION_DATABASE_ID")

    notion = get_client()

    if args.cmd == "list-ports":
        return cmd_list_ports(notion, db_id, args.format)

    if args.cmd == "add-row":
        puerto = args.puerto.strip() or None
        return cmd_add_row(
            notion=notion,
            database_id=db_id,
            alias=args.alias.strip(),
            usuario=args.usuario.strip(),
            hostname=args.hostname.strip(),
            puerto=puerto,
            no_check=args.no_check,
        )

    die("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
