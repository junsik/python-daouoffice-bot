#!/usr/bin/env python3
"""Analyze DaouOffice Messenger SAZ file - extract all API details."""

import json
import os
import re
import sys
import zipfile
from collections import OrderedDict
from urllib.parse import parse_qs, urlparse

# SAZ file to analyze: first CLI arg, or the DAOU_SAZ env var.
SAZ_PATH = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DAOU_SAZ", "")
if not SAZ_PATH:
    sys.exit("usage: python tools/analyze_saz.py <capture.saz>  (or set DAOU_SAZ)")

# Only consider DaouOffice tenant traffic (any *.daouoffice.com sub-domain).
DAOU_HOST_RE = re.compile(r"\.daouoffice\.com", re.IGNORECASE)

def read_all_sessions():
    z = zipfile.ZipFile(SAZ_PATH)
    sessions = []
    for i in range(1, 327):
        prefix = f"{i:03d}"
        try:
            c_raw = z.read(f"raw/{prefix}_c.txt").decode("utf-8", errors="replace")
        except:
            continue
        try:
            s_raw = z.read(f"raw/{prefix}_s.txt").decode("utf-8", errors="replace")
        except:
            continue

        # Parse client request
        client_lines = c_raw.split("\n")
        request_line = client_lines[0]
        parts = request_line.split(" ", 2)
        if len(parts) >= 2:
            method = parts[0]
            full_path = parts[1]
        elif len(parts) == 1:
            method = "GET"
            full_path = parts[0]
        else:
            continue
        headers = parse_headers(client_lines[1:])
        body = ""
        # Body starts after blank line
        blank_idx = None
        for li, line in enumerate(client_lines):
            if line in ("\r", "\r\n", "") and li > 0:
                prev = client_lines[li-1].rstrip("\r")
                if not prev:
                    blank_idx = li
                    break
        # In HTTP text, blank line is empty string in split('\n')
        # find first empty line
        for li, line in enumerate(client_lines):
            if line.strip() == "" and li > 0:
                body_raw = "\n".join(client_lines[li+1:])
                if body_raw.strip():
                    body = body_raw.strip()
                break

        # Parse server response
        server_lines = s_raw.split("\n")
        status_line = server_lines[0]
        s_headers = parse_headers(server_lines[1:])
        s_body = ""
        for li, line in enumerate(server_lines):
            if line.strip() == "" and li > 0:
                s_body_raw = "\n".join(server_lines[li+1:])
                if s_body_raw.strip():
                    s_body = s_body_raw.strip()
                break

        # Full path may be a full URL (e.g. https://yourcompany.daouoffice.com/api/...)
        if full_path.startswith("http"):
            parsed = urlparse(full_path)
            actual_path = parsed.path or "/"
            actual_query = parsed.query or ""
        else:
            actual_path = full_path.split("?")[0] if "?" in full_path else full_path
            actual_query = full_path.split("?")[1] if "?" in full_path else ""

        sess = {
            "index": i,
            "method": method,
            "full_path": full_path,
            "path": actual_path,
            "query": actual_query,
            "headers": headers,
            "body": body,
            "status_line": status_line,
            "s_headers": s_headers,
            "s_body": s_body,
        }
        sessions.append(sess)
    return sessions, z


def parse_headers(lines):
    hdrs = OrderedDict()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            hdrs[k.strip()] = v.strip()
    return hdrs


def try_parse_json(s):
    if not s:
        return None
    try:
        return json.loads(s)
    except:
        # Try stripping BOM
        if s.startswith("\ufeff"):
            try:
                return json.loads(s[1:])
            except:
                pass
        # Try finding JSON block
        m = re.search(r'\{.*\}', s)
        if m:
            try:
                return json.loads(m.group())
            except:
                pass
        # Try decoding gzipped
        return None


def find_sessions(sessions, test_fn):
    return [s for s in sessions if test_fn(s)]


def main():
    sessions, z = read_all_sessions()
    # Filter by full URL containing daouoffice domain
    daou_sessions = [
        s for s in sessions
        if DAOU_HOST_RE.search(s.get("full_path", ""))
        or DAOU_HOST_RE.search(s.get("headers", {}).get("host", ""))
    ]
    print(f"Total HTTP sessions: {len(sessions)}")
    print(f"DaouOffice Messenger sessions: {len(daou_sessions)}")
    print()

    # =========================================================================
    print("=" * 80)
    print("1. AUTHENTICATION FLOW - POST /api/portal/public/auth/login")
    print("=" * 80)
    login_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/api/portal/public/auth/login" in s["full_path"])
    if login_sessions:
        s = login_sessions[0]
        print(f"\n--- Request (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        print("\n  Request Headers:")
        for k, v in s["headers"].items():
            # Mask sensitive values
            show_v = v
            if k.lower() in ("authorization", "cookie", "token"):
                if len(v) > 30:
                    show_v = v[:15] + "..." + v[-10:] if len(v) > 30 else v
            print(f"    {k}: {show_v}")
        print("\n  Request Body:")
        body_json = try_parse_json(s["body"])
        if body_json:
            print(json.dumps(body_json, indent=4, ensure_ascii=False))
        else:
            print(f"    {s['body'][:2000]}")
        print("\n--- Response ---")
        print(f"  {s['status_line']}")
        print("\n  Response Headers:")
        for k, v in s["s_headers"].items():
            if k.lower() not in ("transfer-encoding", "content-encoding"):
                print(f"    {k}: {v}")
        print("\n  Response Body:")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
        else:
            print(s["s_body"][:2000])
    else:
        print("NOT FOUND")

    # Also check for SSO token GET after login
    print("\n--- SSO Token Get (following login) ---")
    sso_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and "/api/portal/common/auth/sso-token" in s["path"])
    if sso_sessions:
        s = sso_sessions[0]
        print(f"\n  {s['method']} {s['full_path']}")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            print(f"    {k}: {v[:100]}")
        print("\n  Response Body (key fields):")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:3000])
        else:
            print(s["s_body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("2. WEBSOCKET CONNECTION - GET /ws/pc")
    print("=" * 80)
    ws_sessions = find_sessions(daou_sessions,
        lambda s: s["path"] == "/ws/pc")
    if ws_sessions:
        for s in ws_sessions:
            print(f"\n--- Request (#{s['index']}) ---")
            print(f"  {s['method']} {s['full_path']}")
            print("\n  Request Headers:")
            for k, v in s["headers"].items():
                print(f"    {k}: {v}")
            print("\n--- Response ---")
            print(f"  {s['status_line']}")
            print("\n  Response Headers:")
            for k, v in s["s_headers"].items():
                print(f"    {k}: {v}")
    print()

    # =========================================================================
    print("=" * 80)
    print("3. CHAT ROOM CREATION - POST /api/chat/room")
    print("=" * 80)
    room_create_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and s["path"] == "/api/chat/room")
    if room_create_sessions:
        for s in room_create_sessions:
            print(f"\n--- Request (#{s['index']}) ---")
            print(f"  {s['method']} {s['full_path']}")
            print("\n  Request Headers:")
            for k, v in s["headers"].items():
                print(f"    {k}: {v[:500]}")
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                print(json.dumps(body_json, indent=4, ensure_ascii=False))
            else:
                print(s["body"][:2000])
            print("\n--- Response ---")
            print(f"  {s['status_line']}")
            print("\n  Response Headers:")
            for k, v in s["s_headers"].items():
                print(f"    {k}: {v}")
            print("\n  Response Body:")
            s_body_json = try_parse_json(s["s_body"])
            if s_body_json:
                print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
            else:
                print(s["s_body"][:2000])
    print()

    # =========================================================================
    print("=" * 80)
    print("4. CHAT ROOM LIST - GET /api/chat/room")
    print("=" * 80)
    room_list_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and s["path"] == "/api/chat/room" and not s["full_path"].endswith("/open"))
    if room_list_sessions:
        s = room_list_sessions[0]
        print(f"\n--- Request (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        if s["query"]:
            params = parse_qs(s["query"])
            print("\n  Query Parameters:")
            for k, vals in params.items():
                print(f"    {k}: {vals}")
        print("\n  Request Headers:")
        for k, v in s["headers"].items():
            print(f"    {k}: {v[:500]}")
        print("\n--- Response ---")
        print(f"  {s['status_line']}")
        print("\n  Response Headers:")
        for k, v in s["s_headers"].items():
            print(f"    {k}: {v}")
        print("\n  Response Body (structure):")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
        else:
            print(s["s_body"][:2000])
    print()

    # =========================================================================
    print("=" * 80)
    print("5. CHAT ROOM OPEN - GET /api/chat/room/{roomId}/open")
    print("=" * 80)
    room_open_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and "/open" in s["path"] and "/chat/room/" in s["path"])
    if room_open_sessions:
        s = room_open_sessions[0]
        print(f"\n--- Request (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        roomId = s["path"].split("/open")[0].split("/chat/room/")[-1]
        print(f"\n  roomId: {roomId}")
        print("\n  Request Headers:")
        for k, v in s["headers"].items():
            print(f"    {k}: {v[:500]}")
        print("\n--- Response ---")
        print(f"  {s['status_line']}")
        print("\n  Response Headers:")
        for k, v in s["s_headers"].items():
            print(f"    {k}: {v}")
        print("\n  Response Body:")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
        else:
            print(s["s_body"][:2000])
    print()

    # =========================================================================
    print("=" * 80)
    print("6. SEND MESSAGE - POST /api/chat/message")
    print("=" * 80)
    msg_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and s["path"] == "/api/chat/message")
    if msg_sessions:
        for s in msg_sessions:
            print(f"\n--- Request (#{s['index']}) ---")
            print(f"  {s['method']} {s['full_path']}")
            print("\n  Request Headers (key headers):")
            for k, v in s["headers"].items():
                if k.lower() in ("content-type", "accept", "authorization", "cookie", "x-session-id",
                                  "x-tenant-id", "x-user-id", "user-id", "tenant-id", "session-id"):
                    print(f"    {k}: {v}")
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                print(json.dumps(body_json, indent=4, ensure_ascii=False))
            else:
                print(s["body"][:2000])
            print("\n--- Response ---")
            print(f"  {s['status_line']}")
            print("\n  Response Body:")
            s_body_json = try_parse_json(s["s_body"])
            if s_body_json:
                print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:3000])
            else:
                print(s["s_body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("7. CHAT HISTORY - GET /api/chat/room/{roomId}/history-open & /chat/range")
    print("=" * 80)
    history_get_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and ("history-open" in s["path"] or "chat/range" in s["path"])
        and "/chat/room/" in s["path"])
    if history_get_sessions:
        s = history_get_sessions[0]
        print(f"\n--- Request (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        roomId = re.search(r'/chat/room/([^/]+)', s["path"])
        if roomId:
            print(f"\n  roomId: {roomId.group(1)}")
        if s["query"]:
            params = parse_qs(s["query"])
            print("\n  Query Parameters:")
            for k, vals in params.items():
                print(f"    {k}: {vals}")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            print(f"    {k}: {v[:500]}")
        print("\n--- Response ---")
        print(f"  {s['status_line']}")
        print("\n  Response Body structure:")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
        else:
            print(s["s_body"][:2000])

    # Also show PUT history-open
    history_put_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "PUT" and "history-open" in s["path"])
    if history_put_sessions:
        s = history_put_sessions[0]
        print(f"\n\n--- PUT {s['path']} (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            if k.lower() not in ("host", "connection", "content-length", "user-agent", "accept-encoding"):
                print(f"    {k}: {v[:500]}")
        print("\n  Request Body:")
        body_json = try_parse_json(s["body"])
        if body_json:
            print(json.dumps(body_json, indent=4, ensure_ascii=False))
        else:
            print(s["body"][:2000])
    print()

    # =========================================================================
    print("=" * 80)
    print("8. MEMBER MANAGEMENT - GET/PUT /api/chat/room/{roomId}/member")
    print("=" * 80)
    member_sessions = find_sessions(daou_sessions,
        lambda s: "/member" in s["path"] and "/chat/room/" in s["path"])
    if member_sessions:
        for s in member_sessions:
            print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
            roomId = re.search(r'/chat/room/([^/]+)', s["path"])
            if roomId:
                print(f"\n  roomId: {roomId.group(1)}")
            print("\n  Request Headers (key):")
            for k, v in s["headers"].items():
                if k.lower() not in ("host", "connection", "content-length", "user-agent", "accept-encoding"):
                    print(f"    {k}: {v[:500]}")
            if s["body"]:
                print("\n  Request Body:")
                body_json = try_parse_json(s["body"])
                if body_json:
                    print(json.dumps(body_json, indent=4, ensure_ascii=False))
                else:
                    print(s["body"][:1000])
            print("\n--- Response ---")
            print(f"  {s['status_line']}")
            print("\n  Response Body:")
            s_body_json = try_parse_json(s["s_body"])
            if s_body_json:
                output = json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)
                # Truncate arrays but show structure
                if len(output) > 5000:
                    print(output[:5000])
                    print(f"\n  ... (truncated, total output: {len(output)} chars)")
                else:
                    print(output)
            else:
                print(s["s_body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("9. USER STATUS / WEBSOCKET KEEPALIVE - POST /api/chat/user/status/connection")
    print("=" * 80)
    status_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/api/chat/user/status/connection" in s["path"])
    if status_sessions:
        for s in status_sessions:
            print(f"\n--- Request (#{s['index']}) ---")
            print(f"  {s['method']} {s['full_path']}")
            print("\n  Request Headers (key):")
            for k, v in s["headers"].items():
                print(f"    {k}: {v[:500]}")
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                print(json.dumps(body_json, indent=4, ensure_ascii=False))
            else:
                print(s["body"][:2000])
            print("\n--- Response ---")
            print(f"  {s['status_line']}")
            print("\n  Request Body (key fields):")
            s_body_json = try_parse_json(s["s_body"])
            if s_body_json:
                print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:2000])
            else:
                print(s["s_body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("10. GRAPHQL QUERIES - POST /api/portal/graphql")
    print("=" * 80)
    graphql_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/api/portal/graphql" in s["path"])
    if graphql_sessions:
        for s in graphql_sessions[:3]:  # First 3 to avoid overwhelming output
            print(f"\n--- Request (#{s['index']}) ---")
            print(f"  {s['method']} {s['full_path']}")
            print("\n  Request Headers (key):")
            for k, v in s["headers"].items():
                if k.lower() not in ("host", "connection", "content-length", "user-agent", "accept-encoding"):
                    print(f"    {k}: {v[:500]}")
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                var_def = body_json.get("variables", {})
                print(f"\n    variables: {json.dumps(var_def, indent=4, ensure_ascii=False, default=str)[:1000]}")
                print(f"\n    operationName: {body_json.get('operationName', '(none)')}")
                # Print query - truncate long ones
                query = body_json.get("query", "")
                # Pretty print the query
                try:
                    # Simple formatting: add newlines around braces
                    query_fmt = re.sub(r'\{', r'\n  {', query.rstrip("}")).rstrip()
                    query_fmt = query_fmt.replace("}", "  }")
                    print("\n    query:")
                    print(f"    {query_fmt[:2000]}")
                except:
                    print(f"    {query[:1000]}")
            else:
                print(s["body"][:2000])
    print()

    # =========================================================================
    print("=" * 80)
    print("11. ORGANIZATION TREE - GET /api/portal/common/organization/tree")
    print("=" * 80)
    org_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and "/organization/tree" in s["path"])
    if org_sessions:
        s = org_sessions[0]
        print(f"\n--- Request (#{s['index']}) ---")
        print(f"  {s['method']} {s['full_path']}")
        if s["query"]:
            params = parse_qs(s["query"])
            print("\n  Query Parameters:")
            for k, vals in params.items():
                print(f"    {k}: {vals}")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            if k.lower() not in ("host", "connection", "user-agent", "accept-encoding"):
                print(f"    {k}: {v[:500]}")
        print("\n--- Response ---")
        print(f"  {s['status_line']}")
        print("\n  Response Body (structure):")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:5000])
        else:
            print(s["s_body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("12. SSO TOKEN & COMPANY INFO")
    print("=" * 80)
    company_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "GET" and "/portal/public/auth/company" in s["path"])
    if company_sessions:
        s = company_sessions[0]
        print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            print(f"    {k}: {v}")
        print("\n  Response Body:")
        s_body_json = try_parse_json(s["s_body"])
        if s_body_json:
            print(json.dumps(s_body_json, indent=4, ensure_ascii=False, default=str)[:2000])
        else:
            print(s["s_body"][:1000])
    print()

    print("=" * 80)
    print("13. ATTACHMENT UPLOAD - POST /api/upload/attach/app")
    print("=" * 80)
    attach_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/api/upload/attach/app" in s["path"])
    if attach_sessions:
        for s in attach_sessions:
            print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
            print("\n  Request Headers:")
            for k, v in s["headers"].items():
                if k.lower() not in ("host", "connection", "user-agent", "accept-encoding"):
                    print(f"    {k}: {v[:500]}")
            print("\n  Response:")
            print(f"    {s['status_line']}")
    print()

    # =========================================================================
    print("=" * 80)
    print("14. MESSAGE READ RECEIPTS - POST /api/chat/message/{id}/read")
    print("=" * 80)
    read_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/read" in s["path"] and "/chat/message/" in s["path"])
    if read_sessions:
        for s in read_sessions[:3]:  # Show first 3
            print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
            print(f"\n  Response: {s['status_line']}")
    print(f"\n  (Total read receipts: {len(read_sessions)})")
    print()

    # =========================================================================
    print("=" * 80)
    print("15. LOGOUT - POST /api/portal/common/auth/logout")
    print("=" * 80)
    logout_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/auth/logout" in s["path"])
    if logout_sessions:
        for s in logout_sessions:
            print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
            print("\n  Request Headers (key):")
            for k, v in s["headers"].items():
                print(f"    {k}: {v[:500]}")
            print(f"\n  Response: {s['status_line']}")
    print()

    # =========================================================================
    print("=" * 80)
    print("16. EMOTICON REACTION - POST /api/chat/message/emoticon")
    print("=" * 80)
    emoticon_sessions = find_sessions(daou_sessions,
        lambda s: s["method"] == "POST" and "/api/chat/message/emoticon" in s["path"])
    if emoticon_sessions:
        for s in emoticon_sessions:
            print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
            print("\n  Request Headers (key):")
            for k, v in s["headers"].items():
                if k.lower() not in ("host", "content-length", "user-agent", "accept-encoding"):
                    print(f"    {k}: {v[:500]}")
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                print(json.dumps(body_json, indent=4, ensure_ascii=False))
            else:
                print(s["body"][:1000])
    print()

    # =========================================================================
    print("=" * 80)
    print("17. PINNED / LOCKED / LEFT / KICKOUT / CHAT SETTINGS")
    print("=" * 80)
    other_ops = find_sessions(daou_sessions,
        lambda s: s["method"] == "PUT" and "/api/chat/room/" in s["path"])
    for s in other_ops:
        print(f"\n--- {s['method']} {s['full_path']} (#{s['index']}) ---")
        print("\n  Request Headers (key):")
        for k, v in s["headers"].items():
            if k.lower() not in ("host", "content-length", "user-agent", "accept-encoding"):
                print(f"    {k}: {v[:500]}")
        if s["body"]:
            print("\n  Request Body:")
            body_json = try_parse_json(s["body"])
            if body_json:
                print(json.dumps(body_json, indent=4, ensure_ascii=False))
            else:
                print(s["body"][:500])
        print(f"\n  Response: {s['status_line']}")
    print()


if __name__ == "__main__":
    main()
