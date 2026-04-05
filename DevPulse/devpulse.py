"""
DevPulse — Intelligent GitHub Activity Engine
Cross-platform | AI-powered | Background daemon
"""

from __future__ import annotations
import os, sys, json, random, logging, datetime, subprocess
import platform, threading, time, socket, hashlib
from pathlib import Path

# ─── Optional imports ────────────────────────────────
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import anthropic
    HAS_AI = True
except ImportError:
    HAS_AI = False

# ══════════════════════════════════════════════════════
#  PATHS & CONSTANTS
# ══════════════════════════════════════════════════════

VERSION      = "2.0.0"
APP_NAME     = "DevPulse"
SYSTEM       = platform.system()   # Windows / Darwin / Linux
IS_TERMUX    = "com.termux" in os.environ.get("PREFIX", "")

BASE_DIR     = Path(__file__).parent.resolve()
CONFIG_FILE  = BASE_DIR / "config.json"
STATE_FILE   = BASE_DIR / "state.json"
LOG_FILE     = BASE_DIR / "devpulse.log"

# ─── Logging ──────────────────────────────────────────
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(APP_NAME)

# ─── Default Config ────────────────────────────────────
DEFAULT_CONFIG: dict = {
    "repos": [],
    "commit_hour_min": 9,
    "commit_hour_max": 22,
    "skip_days_probability": 0.08,
    "multi_commit_probability": 0.25,
    "max_commits_per_day": 3,
    "enabled": True,
    "github_username": "",
    "anthropic_api_key": "",
    "groq_api_key": "",
    "gemini_api_key": "",
    "ai_provider": "anthropic",
    "ai_enabled": False,
    "theme": "dark",
}

# ══════════════════════════════════════════════════════
#  CONFIG & STATE
# ══════════════════════════════════════════════════════

def load_config() -> dict:
    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG.copy())
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg

def save_config(cfg: dict) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    with open(STATE_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def get_log_lines(n: int = 100) -> list[str]:
    if not LOG_FILE.exists():
        return []
    with open(LOG_FILE, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    return [l.rstrip() for l in lines[-n:]]

# ══════════════════════════════════════════════════════
#  SYSTEM ANALYZER
# ══════════════════════════════════════════════════════

class SystemSnapshot:
    """Collect real system metrics for context-aware commits."""

    def __init__(self):
        self.timestamp  = datetime.datetime.now()
        self.hostname   = socket.gethostname()
        self.os_name    = f"{SYSTEM} {platform.release()}"
        self.cpu_pct    = 0.0
        self.ram_total  = 0
        self.ram_used   = 0
        self.ram_pct    = 0.0
        self.disk_total = 0
        self.disk_used  = 0
        self.disk_pct   = 0.0
        self.net_sent   = 0
        self.net_recv   = 0
        self.uptime_h   = 0
        self._collect()

    def _collect(self):
        if not HAS_PSUTIL:
            self.cpu_pct  = round(random.uniform(15, 55), 1)
            self.ram_pct  = round(random.uniform(40, 75), 1)
            self.disk_pct = round(random.uniform(30, 70), 1)
            return
        try:
            self.cpu_pct    = psutil.cpu_percent(interval=0.5)
            vm              = psutil.virtual_memory()
            self.ram_total  = vm.total
            self.ram_used   = vm.used
            self.ram_pct    = vm.percent
            disk            = psutil.disk_usage("/")
            self.disk_total = disk.total
            self.disk_used  = disk.used
            self.disk_pct   = disk.percent
            nio             = psutil.net_io_counters()
            self.net_sent   = nio.bytes_sent
            self.net_recv   = nio.bytes_recv
            boot            = psutil.boot_time()
            self.uptime_h   = round((time.time() - boot) / 3600, 1)
        except Exception as e:
            logger.warning(f"SystemSnapshot error: {e}")

    def summary(self) -> str:
        return (
            f"CPU {self.cpu_pct}% | "
            f"RAM {self.ram_pct}% | "
            f"Disk {self.disk_pct}%"
        )

    def to_markdown(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"""# System Snapshot — {ts}

| Metric | Value |
|--------|-------|
| Host | {self.hostname} |
| OS | {self.os_name} |
| CPU Usage | {self.cpu_pct}% |
| RAM Used | {self.ram_used // (1024**2):,} MB / {self.ram_total // (1024**2):,} MB ({self.ram_pct}%) |
| Disk Used | {self.disk_used // (1024**3):.1f} GB / {self.disk_total // (1024**3):.1f} GB ({self.disk_pct}%) |
| Net Sent | {self.net_sent // (1024**2):,} MB |
| Net Recv | {self.net_recv // (1024**2):,} MB |
| Uptime | {self.uptime_h} hours |

*Captured by DevPulse v{VERSION}*
"""

def analyze_repo(repo_path: str) -> dict:
    """Scan repo for context: languages, recent activity, file count."""
    p = Path(repo_path)
    info: dict = {
        "languages": [],
        "file_count": 0,
        "has_tests": False,
        "has_ci": False,
        "recent_messages": [],
    }
    if not p.exists():
        return info

    ext_map: dict[str, str] = {}
    for fp in p.rglob("*"):
        if fp.is_file() and ".git" not in fp.parts:
            ext = fp.suffix.lower()
            if ext:
                ext_map[ext] = ext_map.get(ext, 0) + 1
            info["file_count"] += 1
            if "test" in fp.name.lower():
                info["has_tests"] = True
            if ".github" in fp.parts or "ci" in fp.name.lower():
                info["has_ci"] = True

    lang_map = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript",
                ".go": "Go", ".rs": "Rust", ".sh": "Shell", ".md": "Markdown",
                ".json": "JSON", ".yml": "YAML", ".cpp": "C++", ".c": "C"}
    info["languages"] = [lang_map[e] for e in sorted(ext_map, key=ext_map.get, reverse=True)
                         if e in lang_map][:4]

    # recent git log
    try:
        res = subprocess.run(
            ["git", "log", "--oneline", "-5"],
            cwd=repo_path, capture_output=True, text=True, timeout=5
        )
        if res.returncode == 0:
            info["recent_messages"] = [l.split(" ", 1)[-1] for l in res.stdout.strip().splitlines() if " " in l]
    except Exception:
        pass

    return info

# ══════════════════════════════════════════════════════
#  STATIC CONTENT LIBRARY (fallback when no AI key)
# ══════════════════════════════════════════════════════

TOPICS = [
    ("Python decorators and metaclasses", "python"),
    ("Linux process scheduling internals", "systems"),
    ("DNS over HTTPS implementation", "networking"),
    ("Binary search tree traversal algorithms", "cs"),
    ("JWT authentication vulnerabilities", "security"),
    ("Docker multi-stage build optimization", "devops"),
    ("Regular expressions: lookaheads and lookbehinds", "python"),
    ("Async I/O event loop mechanics", "python"),
    ("TCP three-way handshake deep dive", "networking"),
    ("Git object model: blobs, trees, commits", "git"),
    ("Memory-mapped files in Python", "python"),
    ("Nmap NSE scripting basics", "security"),
    ("SSH tunneling and port forwarding", "networking"),
    ("Python dataclasses vs attrs vs pydantic", "python"),
    ("Writing efficient Bash scripts", "shell"),
    ("OAuth2 PKCE flow implementation", "security"),
    ("B-tree indexing in databases", "cs"),
    ("Kernel namespaces and cgroups", "systems"),
]

SCRIPTS: dict[str, str] = {
    "network_scanner.py": '''\
"""Lightweight network scanner using raw sockets."""
import socket, concurrent.futures, ipaddress, sys

def scan_port(host: str, port: int, timeout: float = 0.5) -> tuple[int, bool]:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return port, True
    except OSError:
        return port, False

def scan_host(host: str, ports: list[int] | None = None) -> list[int]:
    if ports is None:
        ports = [21,22,23,25,53,80,110,143,443,445,
                 3000,3306,3389,5432,6379,8080,8443,27017]
    open_ports: list[int] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
        for port, is_open in ex.map(lambda p: scan_port(host, p), ports):
            if is_open:
                open_ports.append(port)
    return sorted(open_ports)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    print(f"Scanning {target}...")
    result = scan_host(target)
    for p in result:
        print(f"  {p}/tcp  OPEN")
    if not result:
        print("  No open ports found.")
''',
    "log_analyzer.py": '''\
"""Parse and summarize log files by severity level."""
import re, sys, collections
from pathlib import Path

LEVELS = {"ERROR": 0, "WARNING": 1, "WARN": 1, "INFO": 2, "DEBUG": 3}
PATTERN = re.compile(
    r"(?P<ts>\\d{4}-\\d{2}-\\d{2}[T ]\\d{2}:\\d{2}:\\d{2})"
    r".*?(?P<level>ERROR|WARNING|WARN|INFO|DEBUG)"
    r"\\s+(?P<msg>.+)",
    re.IGNORECASE
)

def analyze(path: str | Path, max_level: str = "WARNING") -> None:
    path = Path(path)
    if not path.exists():
        print(f"File not found: {path}")
        return
    threshold = LEVELS.get(max_level.upper(), 1)
    counts: dict[str, int] = collections.defaultdict(int)
    issues: list[tuple[str, str, str]] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = PATTERN.search(line)
            if m:
                lvl = m.group("level").upper()
                if lvl == "WARN":
                    lvl = "WARNING"
                counts[lvl] += 1
                if LEVELS.get(lvl, 99) <= threshold:
                    issues.append((m.group("ts"), lvl, m.group("msg")[:120]))
    print(f"\\nLog Summary — {path.name}")
    print("-" * 50)
    for lvl in ("ERROR", "WARNING", "INFO", "DEBUG"):
        if counts[lvl]:
            print(f"  {lvl:<10} {counts[lvl]:>6}")
    print(f"\\nTop issues (level <= {max_level}):")
    for ts, lvl, msg in issues[-20:]:
        print(f"  [{ts}] {lvl}: {msg}")

if __name__ == "__main__":
    analyze(sys.argv[1] if len(sys.argv) > 1 else "/var/log/syslog")
''',
    "env_checker.py": '''\
"""Check development environment health and report missing tools."""
import shutil, subprocess, sys, platform

TOOLS = [
    ("python3",   "Python 3",        "python3 --version"),
    ("git",       "Git",             "git --version"),
    ("docker",    "Docker",          "docker --version"),
    ("node",      "Node.js",         "node --version"),
    ("npm",       "npm",             "npm --version"),
    ("pip",       "pip",             "pip --version"),
    ("curl",      "curl",            "curl --version"),
    ("ssh",       "OpenSSH",         "ssh -V"),
    ("vim",       "Vim",             "vim --version"),
    ("tmux",      "tmux",            "tmux -V"),
]

def check() -> None:
    print(f"\\nEnvironment Check — {platform.node()} ({platform.system()} {platform.release()})")
    print("=" * 60)
    ok = fail = 0
    for cmd, name, version_cmd in TOOLS:
        found = shutil.which(cmd) is not None
        if found:
            try:
                r = subprocess.run(version_cmd.split(), capture_output=True, text=True, timeout=3)
                ver = (r.stdout or r.stderr).split("\\n")[0].strip()[:40]
            except Exception:
                ver = "installed"
            print(f"  [OK] {name:<15} {ver}")
            ok += 1
        else:
            print(f"  [--] {name:<15} not found")
            fail += 1
    print(f"\\n  {ok} available, {fail} missing")

if __name__ == "__main__":
    check()
''',
    "git_stats.py": '''\
"""Generate contribution statistics from a local git repository."""
import subprocess, sys, collections, datetime
from pathlib import Path

def get_stats(repo: str = ".") -> None:
    def git(*args: str) -> str:
        r = subprocess.run(
            ["git", *args], cwd=repo,
            capture_output=True, text=True, timeout=10
        )
        return r.stdout.strip()

    log = git("log", "--format=%ae|%ad|%s", "--date=short")
    if not log:
        print("No commits found.")
        return

    by_author: dict = collections.defaultdict(int)
    by_date:   dict = collections.defaultdict(int)
    by_dow:    dict = collections.defaultdict(int)
    messages:  list = []

    for line in log.splitlines():
        parts = line.split("|", 2)
        if len(parts) < 3:
            continue
        author, date_str, msg = parts
        by_author[author] += 1
        by_date[date_str] += 1
        try:
            d = datetime.date.fromisoformat(date_str)
            by_dow[d.strftime("%A")] += 1
        except ValueError:
            pass
        messages.append(msg)

    total = sum(by_author.values())
    print(f"\\nGit Stats — {Path(repo).resolve().name}")
    print(f"Total commits: {total}")
    print("\\nTop contributors:")
    for a, c in sorted(by_author.items(), key=lambda x: -x[1])[:5]:
        bar = "█" * min(c, 40)
        print(f"  {a[:30]:<30} {c:>4}  {bar}")
    print("\\nActivity by day of week:")
    days = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    for day in days:
        c = by_dow.get(day, 0)
        bar = "█" * min(c, 30)
        print(f"  {day:<12} {c:>4}  {bar}")

if __name__ == "__main__":
    get_stats(sys.argv[1] if len(sys.argv) > 1 else ".")
''',
    "api_tester.py": '''\
"""Simple HTTP API endpoint tester with timing and status checks."""
import urllib.request, urllib.error, json, time, sys
from typing import Any

HEADERS_DEFAULT = {
    "User-Agent": "DevPulse-APITester/1.0",
    "Accept": "application/json",
}

def test_endpoint(
    url: str,
    method: str = "GET",
    payload: Any = None,
    expected_status: int = 200,
    timeout: int = 10,
    headers: dict | None = None,
) -> dict:
    hdrs = {**HEADERS_DEFAULT, **(headers or {})}
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode()
        hdrs["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    start = time.perf_counter()
    result = {
        "url": url, "method": method,
        "status": None, "ok": False,
        "latency_ms": None, "body_len": 0, "error": None,
    }
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            result.update({
                "status": resp.status,
                "ok": resp.status == expected_status,
                "body_len": len(body),
            })
    except urllib.error.HTTPError as e:
        result.update({"status": e.code, "error": str(e)})
    except Exception as e:
        result["error"] = str(e)
    finally:
        result["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)

    icon = "OK" if result["ok"] else "FAIL"
    print(f"  [{icon}] {method} {url}")
    print(f"       Status: {result['status']} | {result['latency_ms']} ms | {result['body_len']} bytes")
    if result["error"]:
        print(f"       Error: {result['error']}")
    return result

if __name__ == "__main__":
    urls = sys.argv[1:] or [
        "https://httpbin.org/get",
        "https://httpbin.org/status/404",
    ]
    print("API Endpoint Tests")
    print("=" * 50)
    results = [test_endpoint(u) for u in urls]
    passed = sum(1 for r in results if r["ok"])
    print(f"\\n  {passed}/{len(results)} tests passed")
''',
}

# ── Note templates — varied, realistic, non-repetitive ────────────

_NOTE_FORMATS = [
    # Format A: quick reference card
    lambda topic, cat, today: f"""# {topic}
{today}

Quick ref — things I keep forgetting.

## The short version
{topic} is mostly about trade-offs. Fast path vs correct path,
simple code vs flexible code. Pick based on actual constraints,
not assumptions.

## Commands / snippets I actually use

```bash
# placeholder — fill in from docs
man {topic.split()[0].lower()}
```

## Gotchas
- Edge cases show up in production, not in tests
- Default settings are rarely optimal for your use case
- Read the source when docs are wrong

## Links
- https://docs.python.org (or relevant docs)
- Stack Overflow: [{topic}](https://stackoverflow.com/search?q={topic.replace(" ", "+")})
""",

    # Format B: problem → solution
    lambda topic, cat, today: f"""# {topic} — notes
{today}

## Problem I was trying to solve
Needed to understand {topic.lower()} better.
Spent time reading docs + a few blog posts.

## What I learned

The key thing: {topic.split()[0]} behaviour depends heavily on context.
What works in dev often breaks in prod because of resource limits,
timing, or state assumptions.

## Code that helped me understand it

```python
# Minimal working example
import sys

def main():
    # TODO: fill in real example
    print(f"Working with {topic.split()[0].lower()}")

if __name__ == "__main__":
    main()
```

## Still unclear
- How this behaves under load
- Whether there's a simpler abstraction

## Next
- Try it in a real project
- Benchmark if performance matters
""",

    # Format C: comparison / decision log
    lambda topic, cat, today: f"""# {topic}
{today}

## Context
Looking at options for a {cat} project. Needed to decide
whether {topic.lower()} was the right approach.

## Options considered

| Approach | Pros | Cons |
|----------|------|------|
| {topic.split()[0]} | Well-documented, stable | Overhead |
| Alternative | Lighter | Less ecosystem |
| DIY | Full control | Maintenance burden |

## Decision
Went with standard {topic.split()[0].lower()} because the ecosystem
support outweighed the overhead for this use case.

## Lessons from implementation
- Start with the simplest thing that works
- Profile before optimizing
- Documentation ≠ real behaviour under load
""",

    # Format D: debugging session log
    lambda topic, cat, today: f"""# Debugging: {topic}
{today}

## What broke
Something behaving unexpectedly related to {topic.lower()}.

## How I debugged it

```bash
# Check the obvious stuff first
python -c "import sys; print(sys.version)"
# Then logs
tail -f /var/log/syslog  # or equivalent
```

Turned out the issue was an assumption I made about default
config. Always check defaults.

## Fix
Changed config, added a check, added a test for the edge case.

## What I'd do differently
Not assume defaults are sane. Read config docs first, implement second.

## Reference
- Issue was similar to: https://github.com (search for your error)
""",

    # Format E: reading notes
    lambda topic, cat, today: f"""# Reading notes: {topic}
{today}

Going through docs / a post on {topic.lower()}.
Writing this to force active reading.

## Main points

1. The fundamentals matter more than the fancy features
2. {topic.split()[0]} has sharp edges when used at scale
3. The abstractions leak when you push limits

## Quote that stuck
> "Make it work, make it right, make it fast — in that order."

## Things to try
- [ ] Minimal example in isolation
- [ ] Test with realistic data size
- [ ] Profile memory, not just CPU

## Related topics
- {cat} internals
- System design patterns
- Performance measurement
""",
]

def _note_template(topic: str, category: str) -> str:
    today = datetime.date.today().isoformat()
    fmt = random.choice(_NOTE_FORMATS)
    return fmt(topic, category, today)

OSINT_NOTES = [
    """\
# Reconnaissance: Subdomain Enumeration Techniques
*{date}*

## Passive Methods
Certificate transparency logs are publicly searchable and often reveal subdomains
before they become broadly known.

```bash
# crt.sh query
curl -s "https://crt.sh/?q=%25.{domain}&output=json" | jq '.[].name_value' | sort -u
```

## Active DNS Bruteforce
```bash
# Using a wordlist with massDNS
massdns -r resolvers.txt -t A wordlist.txt -o S > results.txt
grep "NOERROR" results.txt | cut -d' ' -f1
```

## Tools Comparison
| Tool | Speed | Accuracy | Passive |
|------|-------|----------|---------|
| subfinder | Fast | High | Yes |
| amass | Slow | Very High | Both |
| assetfinder | Fast | Medium | Yes |
| dnsx | Very fast | High | No |

## Notes
Always verify with multiple sources before acting on results.
False positives are common in passive enumeration.

---
*{date}*
""",
    """\
# Network Protocol Analysis: TLS Handshake
*{date}*

## TLS 1.3 Handshake Phases

### 1. ClientHello
Client sends supported cipher suites, TLS version, random nonce,
and key shares for preferred groups (X25519, P-256).

### 2. ServerHello + Encrypted Extensions
Server selects parameters and immediately begins encryption.
TLS 1.3 eliminates the server key exchange message entirely.

### Wireshark Capture Tips
```
# Filter for TLS handshake only
tls.handshake
# Show certificate details
tls.handshake.type == 11
# Find SNI (Server Name Indication)
tls.handshake.extensions_server_name
```

## Common Issues
- Mixed content (TLS + HTTP resources) breaks HSTS
- Certificate chain ordering matters for some clients
- SNI required for virtual hosting — can expose target hostname

---
*{date}*
""",
]

# ══════════════════════════════════════════════════════
#  AI CONTENT ENGINE
# ══════════════════════════════════════════════════════

class AIEngine:
    """Multi-provider AI engine: Anthropic, Groq, Gemini."""

    SYSTEM = (
        "You write content for a developer's GitHub repository. "
        "Style: terse, technical, practical. Like a senior engineer's notes. "
        "No filler. No AI-sounding phrases. No preamble. Just the content."
    )

    def __init__(self, provider: str, api_key: str):
        self.provider = provider
        self.api_key  = api_key
        self._client  = None
        if provider == "anthropic":
            if not HAS_AI:
                raise RuntimeError("pip install anthropic")
            import anthropic as _ant
            self._client = _ant.Anthropic(api_key=api_key)

    def _call(self, prompt: str, max_tokens: int = 800) -> str:
        try:
            if self.provider == "anthropic":
                msg = self._client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=max_tokens,
                    system=self.SYSTEM,
                    messages=[{"role": "user", "content": prompt}],
                )
                return msg.content[0].text.strip()

            elif self.provider == "groq":
                import urllib.request, json as _json
                body = _json.dumps({
                    "model": "llama3-8b-8192",
                    "messages": [
                        {"role": "system", "content": self.SYSTEM},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.8,
                }).encode()
                req = urllib.request.Request(
                    "https://api.groq.com/openai/v1/chat/completions",
                    data=body,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"},
                )
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = _json.loads(r.read())
                return data["choices"][0]["message"]["content"].strip()

            elif self.provider == "gemini":
                import urllib.request, json as _json
                body = _json.dumps({
                    "contents": [{"parts": [{"text": self.SYSTEM + "\n\n" + prompt}]}],
                    "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.8},
                }).encode()
                url = (f"https://generativelanguage.googleapis.com/v1beta/"
                       f"models/gemini-1.5-flash:generateContent?key={self.api_key}")
                req = urllib.request.Request(url, data=body,
                                             headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = _json.loads(r.read())
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()

        except Exception as e:
            logger.warning(f"AI call failed ({self.provider}): {e}")
            return ""

    def generate_note(self, topic: str, repo_info: dict) -> str:
        langs = ", ".join(repo_info.get("languages", ["Python"])) or "Python"
        prompt = (
            f"Write a concise technical learning note about: {topic}\n"
            f"The developer works primarily with: {langs}\n"
            f"Format as Markdown. Include a short code example if relevant.\n"
            f"Max 300 words. Today: {datetime.date.today().isoformat()}"
        )
        result = self._call(prompt, 600)
        return result or _note_template(topic, "software")

    def generate_script(self, repo_info: dict) -> tuple[str, str]:
        langs = repo_info.get("languages", [])
        lang  = langs[0] if langs else "Python"
        topics_str = ", ".join(TOPICS[i][0] for i in random.sample(range(len(TOPICS)), 3))
        prompt = (
            f"Write a small, self-contained, working {lang} utility script "
            f"(40-80 lines). Pick something related to one of: {topics_str}. "
            f"Include a docstring, type hints if Python, and a runnable __main__ block. "
            f"Return: first line = filename (e.g. 'my_tool.py'), "
            f"rest = file contents. No markdown fences."
        )
        result = self._call(prompt, 700)
        if result and "\n" in result:
            first, rest = result.split("\n", 1)
            fname = first.strip().lstrip("# ").strip()
            if not fname.endswith((".py", ".sh", ".js")):
                fname = "utility_tool.py"
            return fname, rest.strip()
        name, code = random.choice(list(SCRIPTS.items()))
        return name, code

    def generate_commit_message(self, files_changed: list[str]) -> str:
        flist = ", ".join(files_changed[:3])
        prompt = (
            f"Write a concise git commit message (max 72 chars) for changes to: {flist}. "
            f"Use imperative mood. No ticket numbers. No generic phrases like 'update files'."
        )
        result = self._call(prompt, 80)
        return result or f"Update {files_changed[0] if files_changed else 'project files'}"

# ══════════════════════════════════════════════════════
#  LOCAL CONTENT (no AI key required)
# ══════════════════════════════════════════════════════

def local_generate_note() -> tuple[str, str]:
    topic, cat = random.choice(TOPICS)
    today = datetime.date.today().isoformat()
    rid   = random.randint(100, 999)
    fname = f"notes/note_{today}_{rid}.md"
    return fname, _note_template(topic, cat)

def local_generate_script() -> tuple[str, str]:
    name, code = random.choice(list(SCRIPTS.items()))
    return f"scripts/{name}", code

def local_generate_syslog(snap: SystemSnapshot) -> tuple[str, str]:
    today = datetime.date.today().isoformat()
    fname = f"logs/syslog_{today}.md"
    return fname, snap.to_markdown()

def local_generate_osint() -> tuple[str, str]:
    today = datetime.date.today().isoformat()
    rid   = random.randint(100, 999)
    fname = f"research/note_{today}_{rid}.md"
    content = random.choice(OSINT_NOTES).replace("{date}", today).replace("{domain}", "example.com")
    return fname, content

def local_generate_readme(repo_path: str) -> tuple[str, str]:
    today = datetime.date.today().isoformat()
    readme_path = Path(repo_path) / "README.md"
    badge = f"\n\n> Last sync: **{today}**\n"
    if readme_path.exists():
        with open(readme_path, encoding="utf-8") as f:
            content = f.read()
        lines = [l for l in content.splitlines() if "Last sync:" not in l]
        content = "\n".join(lines) + badge
    else:
        content = f"""# Dev Notes

Personal knowledge base — scripts, research, and daily logs.

## Structure
- `notes/` — Technical learning notes
- `scripts/` — Utility tools and experiments
- `logs/` — System snapshots
- `research/` — Security and networking research
{badge}"""
    return "README.md", content

# ══════════════════════════════════════════════════════
#  GIT OPERATIONS
# ══════════════════════════════════════════════════════

def _run(cmd: str | list, cwd: str | None = None) -> tuple[int, str, str]:
    if isinstance(cmd, str):
        cmd = cmd.split()
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def check_git() -> bool:
    code, _, _ = _run("git --version")
    return code == 0

def check_internet() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

def get_default_branch(repo_path: str) -> str:
    _, out, _ = _run("git symbolic-ref --short HEAD", cwd=repo_path)
    return out or "main"

def init_repo(repo_path: str) -> None:
    p = Path(repo_path)
    for folder in ["notes", "scripts", "logs", "research"]:
        (p / folder).mkdir(parents=True, exist_ok=True)
    code, _, _ = _run("git rev-parse --git-dir", cwd=repo_path)
    if code != 0:
        _run("git init", cwd=repo_path)
        logger.info(f"Initialized git repo at {repo_path}")

def write_file(repo_path: str, rel_path: str, content: str) -> str:
    full = Path(repo_path) / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return rel_path

def do_commit(repo_path: str, msg: str) -> bool:
    _run("git add -A", cwd=repo_path)
    code, _, err = _run(["git", "commit", "-m", msg], cwd=repo_path)
    if code == 0:
        logger.info(f"[{Path(repo_path).name}] Committed: {msg}")
        return True
    logger.warning(f"Commit failed: {err}")
    return False

def do_push(repo_path: str) -> bool:
    if not check_internet():
        logger.warning("No internet — push skipped")
        return False
    branch = get_default_branch(repo_path)
    code, _, err = _run(f"git push origin {branch}", cwd=repo_path)
    if code == 0:
        logger.info(f"[{Path(repo_path).name}] Push OK")
        return True
    # try setting upstream
    code2, _, err2 = _run(f"git push --set-upstream origin {branch}", cwd=repo_path)
    if code2 == 0:
        logger.info(f"[{Path(repo_path).name}] Push OK (upstream set)")
        return True
    logger.warning(f"Push failed: {err2 or err}")
    return False

def has_remote(repo_path: str) -> bool:
    code, out, _ = _run("git remote", cwd=repo_path)
    return code == 0 and bool(out.strip())

# ══════════════════════════════════════════════════════
#  COMMIT ORCHESTRATOR
# ══════════════════════════════════════════════════════

COMMIT_MSGS = [
    "Add {topic} notes",
    "Update {topic} documentation",
    "Add utility: {fname}",
    "Log system snapshot — {date}",
    "Research notes: {topic}",
    "Refactor {fname}",
    "Add {fname}",
    "Document {topic} patterns",
    "Daily log — {date}",
    "Improve {fname}",
]

def _pick_msg(topic: str = "", fname: str = "") -> str:
    today = datetime.date.today().strftime("%b %d")
    t     = random.choice(COMMIT_MSGS)
    return t.format(
        topic=topic or random.choice(TOPICS)[0].split()[0].lower(),
        fname=fname or "utilities",
        date=today,
    )

def perform_activity(
    repo_path: str,
    ai_engine: AIEngine | None = None,
    status_cb=None,
) -> list[tuple[bool, bool, str]]:
    results: list[tuple[bool, bool, str]] = []
    snap = SystemSnapshot()
    repo_info = analyze_repo(repo_path)

    def status(msg: str):
        logger.info(msg)
        if status_cb:
            status_cb(msg)

    generators = [
        ("note",    0.55),
        ("script",  0.40),
        ("syslog",  0.35),
        ("osint",   0.25),
        ("readme",  0.15),
    ]
    chosen = [g for g, p in generators if random.random() < p]
    if not chosen:
        chosen = ["note"]

    for gen in chosen:
        rel_path = msg = ""

        if gen == "note":
            if ai_engine:
                topic, _ = random.choice(TOPICS)
                content  = ai_engine.generate_note(topic, repo_info)
                rel_path = f"notes/note_{datetime.date.today().isoformat()}_{random.randint(100,999)}.md"
                msg      = _pick_msg(topic=topic.split()[0].lower())
            else:
                rel_path, content = local_generate_note()
                msg = _pick_msg(topic=rel_path.split("_")[2] if "_" in rel_path else "notes")

        elif gen == "script":
            if ai_engine:
                fname, content = ai_engine.generate_script(repo_info)
                rel_path = f"scripts/{fname}"
                msg      = ai_engine.generate_commit_message([fname])
            else:
                rel_path, content = local_generate_script()
                msg = _pick_msg(fname=Path(rel_path).name)

        elif gen == "syslog":
            rel_path, content = local_generate_syslog(snap)
            msg = f"Log system metrics — {datetime.date.today().isoformat()}"

        elif gen == "osint":
            rel_path, content = local_generate_osint()
            msg = _pick_msg(topic="network-research")

        elif gen == "readme":
            rel_path, content = local_generate_readme(repo_path)
            msg = f"Update README — {datetime.date.today().isoformat()}"

        if not rel_path:
            continue

        write_file(repo_path, rel_path, content)
        status(f"Generated: {rel_path}")

        committed = do_commit(repo_path, msg)
        pushed    = do_push(repo_path) if committed and has_remote(repo_path) else False
        results.append((committed, pushed, msg))

        if len(chosen) > 1:
            time.sleep(random.randint(3, 10))

    return results

# ══════════════════════════════════════════════════════
#  DAILY SCHEDULER
# ══════════════════════════════════════════════════════

def already_committed_today(repo_path: str) -> bool:
    state = load_state()
    return state.get(f"last_{repo_path}") == datetime.date.today().isoformat()

def mark_committed(repo_path: str) -> None:
    state = load_state()
    state[f"last_{repo_path}"] = datetime.date.today().isoformat()
    state[f"commits_{datetime.date.today().isoformat()}"] = \
        state.get(f"commits_{datetime.date.today().isoformat()}", 0) + 1
    save_state(state)

def total_commits() -> int:
    state = load_state()
    return sum(v for k, v in state.items() if k.startswith("commits_"))

def run_automation(status_cb=None, force: bool = False) -> list:
    cfg = load_config()

    if not cfg.get("enabled", True):
        if status_cb: status_cb("Automation disabled")
        return []

    if not check_git():
        if status_cb: status_cb("ERROR: git not found in PATH")
        return []

    repos = cfg.get("repos", [])
    if not repos:
        if status_cb: status_cb("No repositories configured")
        return []

    # Build AI engine if configured
    ai_engine: AIEngine | None = None
    if cfg.get("ai_enabled"):
        provider = cfg.get("ai_provider", "anthropic")
        key_map  = {"anthropic": "anthropic_api_key",
                    "groq":      "groq_api_key",
                    "gemini":    "gemini_api_key"}
        api_key  = cfg.get(key_map.get(provider, "anthropic_api_key"), "")
        if api_key:
            try:
                ai_engine = AIEngine(provider, api_key)
                if status_cb: status_cb(f"AI engine active ({provider})")
            except Exception as e:
                if status_cb: status_cb(f"AI engine init failed: {e}")
        else:
            if status_cb: status_cb("AI enabled but no key found — using built-in library")

    all_results: list = []
    for repo_path in repos:
        if already_committed_today(repo_path) and not force:
            if status_cb: status_cb(f"Already committed today — {Path(repo_path).name}")
            continue

        skip_p = cfg.get("skip_days_probability", 0.08)
        if random.random() < skip_p and not force:
            if status_cb: status_cb("Skip day (realistic behavior)")
            continue

        init_repo(repo_path)

        n = 1
        if random.random() < cfg.get("multi_commit_probability", 0.25):
            n = random.randint(2, cfg.get("max_commits_per_day", 3))

        if status_cb: status_cb(f"Making {n} commit(s) → {Path(repo_path).name}")

        for _ in range(n):
            res = perform_activity(repo_path, ai_engine=ai_engine, status_cb=status_cb)
            all_results.extend(res)
            if n > 1:
                time.sleep(random.randint(5, 15))

        mark_committed(repo_path)

    return all_results

# ══════════════════════════════════════════════════════
#  BACKGROUND SCHEDULER THREAD
# ══════════════════════════════════════════════════════

_stop_evt = threading.Event()
_thread: threading.Thread | None = None

def _loop(status_cb=None):
    logger.info("Scheduler started — background daemon active")
    if status_cb: status_cb("Scheduler started — will auto-commit daily")
    while not _stop_evt.is_set():
        cfg = load_config()
        if cfg.get("enabled", True):
            now  = datetime.datetime.now()
            hlo  = cfg.get("commit_hour_min", 9)
            hhi  = cfg.get("commit_hour_max", 22)
            if hlo <= now.hour < hhi:
                run_automation(status_cb=status_cb)
        # Sleep 1 hour, wake up and check again
        _stop_evt.wait(3600)
    logger.info("Scheduler stopped")
    if status_cb: status_cb("Scheduler stopped")

def start_scheduler(status_cb=None) -> bool:
    global _thread, _stop_evt
    if _thread and _thread.is_alive():
        return False
    _stop_evt.clear()
    _thread = threading.Thread(target=_loop, args=(status_cb,), daemon=True)
    _thread.start()
    return True

def stop_scheduler() -> bool:
    _stop_evt.set()
    return True

def is_running() -> bool:
    return _thread is not None and _thread.is_alive()

# ══════════════════════════════════════════════════════
#  CROSS-PLATFORM STARTUP REGISTRATION
# ══════════════════════════════════════════════════════

def register_startup() -> tuple[bool, str]:
    script = Path(__file__).parent / "cli.py"

    if IS_TERMUX:
        boot_dir = Path.home() / ".termux" / "boot"
        boot_dir.mkdir(parents=True, exist_ok=True)
        boot_script = boot_dir / "devpulse.sh"
        with open(boot_script, "w", encoding="utf-8") as f:
            f.write(f"#!/data/data/com.termux/files/usr/bin/bash\n"
                    f"python '{script}' start --silent &\n")
        boot_script.chmod(0o755)
        return True, f"Startup script created: {boot_script}"

    elif SYSTEM == "Windows":
        task       = "DevPulse"
        python_exe = sys.executable
        script_str = str(script)
        # Fallback: write .bat to Startup folder (no Admin needed, always works)
        try:
            startup_dir = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) /                           "Microsoft" / "Windows" / "Start Menu" /                           "Programs" / "Startup"
            startup_dir.mkdir(parents=True, exist_ok=True)
            bat = startup_dir / "devpulse.bat"
            with open(bat, "w", encoding="utf-8") as f:
                f.write(f'@echo off\nstart /min "" "{python_exe}" "{script_str}" start --silent\n')
            return True, f"Auto-start registered (Startup folder): {bat}"
        except Exception as bat_err:
            # Try schtasks as last resort
            cmd = [
                "schtasks", "/Create", "/F",
                "/TN", task, "/SC", "ONLOGON",
                "/TR", f'"{python_exe}" "{script_str}" start --silent',
                "/RL", "HIGHEST"
            ]
            code, _, err = _run(cmd)
            if code == 0:
                return True, f"Task Scheduler: '{task}' registered"
            return False, f"Startup failed: {bat_err} | schtasks: {err}"

    elif SYSTEM == "Darwin":
        plist_dir  = Path.home() / "Library" / "LaunchAgents"
        plist_dir.mkdir(parents=True, exist_ok=True)
        plist_path = plist_dir / "com.devpulse.agent.plist"
        python_bin = sys.executable
        plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>              <string>com.devpulse.agent</string>
  <key>ProgramArguments</key>
  <array>
    <string>{python_bin}</string>
    <string>{script}</string>
    <string>start</string>
    <string>--silent</string>
  </array>
  <key>RunAtLoad</key>          <true/>
  <key>KeepAlive</key>          <false/>
  <key>StandardOutPath</key>    <string>{LOG_FILE}</string>
  <key>StandardErrorPath</key>  <string>{LOG_FILE}</string>
</dict>
</plist>"""
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(plist)
        _run(f"launchctl load {plist_path}")
        return True, f"LaunchAgent installed: {plist_path}"

    else:  # Linux
        service_dir  = Path.home() / ".config" / "systemd" / "user"
        service_dir.mkdir(parents=True, exist_ok=True)
        service_path = service_dir / "devpulse.service"
        python_bin   = sys.executable
        service = f"""[Unit]
Description=DevPulse GitHub Activity Daemon
After=network.target

[Service]
Type=simple
ExecStart={python_bin} {script} start --silent
Restart=on-failure
RestartSec=60

[Install]
WantedBy=default.target
"""
        with open(service_path, "w", encoding="utf-8") as f:
            f.write(service)
        _run("systemctl --user daemon-reload")
        _run("systemctl --user enable devpulse")
        _run("systemctl --user start devpulse")
        return True, f"systemd user service installed: {service_path}"

def unregister_startup() -> tuple[bool, str]:
    if SYSTEM == "Windows":
        code, _, _ = _run('schtasks /Delete /TN "DevPulse" /F')
        return code == 0, "Startup task removed"
    elif SYSTEM == "Darwin":
        p = Path.home() / "Library" / "LaunchAgents" / "com.devpulse.agent.plist"
        _run(f"launchctl unload {p}")
        try: p.unlink()
        except Exception: pass
        return True, "LaunchAgent removed"
    elif IS_TERMUX:
        p = Path.home() / ".termux" / "boot" / "devpulse.sh"
        try: p.unlink(); return True, "Boot script removed"
        except Exception: return False, "Boot script not found"
    else:
        _run("systemctl --user disable devpulse")
        _run("systemctl --user stop devpulse")
        return True, "systemd service removed"
