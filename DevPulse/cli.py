"""
DevPulse — Interactive CLI
Numbered menu, no typing commands needed
"""
from __future__ import annotations
import sys, os, argparse, datetime, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import devpulse as core

R   = "\033[91m"; G  = "\033[92m"; Y  = "\033[93m"
B   = "\033[94m"; C  = "\033[96m"; W  = "\033[97m"
DIM = "\033[2m";  RST = "\033[0m"; BOLD = "\033[1m"

if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
    R = G = Y = B = C = W = DIM = RST = BOLD = ""

def _clr(): print("\033[2J\033[H", end="")

LOGO = f"""
{C}  ██████╗ ███████╗██╗   ██╗██████╗ ██╗   ██╗██╗     ███████╗███████╗
  ██╔══██╗██╔════╝██║   ██║██╔══██╗██║   ██║██║     ██╔════╝██╔════╝
  ██║  ██║█████╗  ██║   ██║██████╔╝██║   ██║██║     ███████╗█████╗
  ██║  ██║██╔══╝  ╚██╗ ██╔╝██╔═══╝ ██║   ██║██║     ╚════██║██╔══╝
  ██████╔╝███████╗ ╚████╔╝ ██║     ╚██████╔╝███████╗███████║███████╗
  ╚═════╝ ╚══════╝  ╚═══╝  ╚═╝      ╚═════╝ ╚══════╝╚══════╝╚══════╝{RST}
  {DIM}v{core.VERSION}  ·  Intelligent GitHub Activity Engine{RST}
"""

def ok(m):   print(f"  {G}ok{RST}  {m}")
def err(m):  print(f"  {R}!!{RST}  {m}")
def warn(m): print(f"  {Y}!{RST}   {m}")
def info(m): print(f"  {B}->{RST}  {m}")

def status_cb(msg):
    m = msg.lower()
    if any(w in m for w in ("error","fail")): err(msg)
    elif any(w in m for w in ("warn","skip")): warn(msg)
    elif any(w in m for w in ("ok","push","commit","success","generat","made")): ok(msg)
    else: info(msg)

def _sep(c="─", n=54): print(f"  {DIM}{c*n}{RST}")
def _pause(): print(); input(f"  {DIM}Press Enter to return...{RST}")

def _header(t):
    _sep("═"); print(f"  {BOLD}{t}{RST}"); _sep()

def _live_status():
    cfg     = core.load_config()
    running = core.is_running()
    ai_key  = cfg.get("anthropic_api_key","") or cfg.get("groq_api_key","") or cfg.get("gemini_api_key","")
    ai_on   = cfg.get("ai_enabled") and bool(ai_key)
    net     = core.check_internet()
    git     = core.check_git()
    r = f"{G}RUNNING{RST}" if running else f"{R}STOPPED{RST}"
    a = f"{G}ON{RST}"      if ai_on  else f"{DIM}OFF{RST}"
    n = f"{G}+{RST}"       if net    else f"{R}-{RST}"
    g = f"{G}+{RST}"       if git    else f"{R}-{RST}"
    print(f"  Scheduler {r}  AI {a}  Net {n}  Git {g}")

def main_menu():
    while True:
        _clr()
        print(LOGO)
        _live_status()
        print()
        cfg   = core.load_config()
        state = core.load_state()
        today = datetime.date.today().isoformat()
        repos = cfg.get("repos",[])
        done  = any(state.get(f"last_{r}") == today for r in repos)

        _sep("═")
        print(f"  {BOLD}Menu{RST}")
        _sep()
        items = [
            ("1","Run Now",         "Commit to GitHub right now",       G),
            ("2","Start Scheduler", "Auto-commit daily in background",   B),
            ("3","Stop Scheduler",  "Pause automation",                  Y),
            ("4","Status",          "Check everything",                  C),
            ("5","Setup Repos",     "Add repositories",                  W),
            ("6","Git Remote",      "Connect repo to GitHub (token)",    W),
            ("7","Register Startup","Auto-run on PC boot",               W),
            ("8","AI Settings",     "Free AI: Groq / Gemini",            C),
            ("9","View Logs",       "Activity history",                  DIM),
            ("0","Exit",            "",                                  DIM),
        ]
        for key,label,desc,color in items:
            dot = f"{G}*{RST} " if (key=="2" and core.is_running()) else "  "
            print(f"  {dot}{color}[{key}]{RST}  {label}  {DIM}{desc}{RST}")

        _sep()
        today_txt = f"{G}committed today {RST}" if done else f"{Y}not yet today{RST}"
        print(f"  {today_txt} | commits: {C}{core.total_commits()}{RST} | repos: {len(repos)}")
        _sep()
        ch = input(f"\n  {BOLD}[0-9]:{RST} ").strip()
        print()

        if   ch=="1": menu_run_now()
        elif ch=="2": menu_start()
        elif ch=="3": menu_stop()
        elif ch=="4": menu_status()
        elif ch=="5": menu_setup_repos()
        elif ch=="6": menu_git_remote()
        elif ch=="7": menu_startup()
        elif ch=="8": menu_ai_settings()
        elif ch=="9": menu_logs()
        elif ch=="0": print(f"  {DIM}Bye.{RST}\n"); break
        else: warn("Use 0-9"); time.sleep(0.6)

def menu_run_now():
    _header("Run Now")
    cfg = core.load_config()
    if not cfg.get("repos"):
        err("No repos configured. Use option [5] first.")
        _pause(); return
    results = core.run_automation(status_cb=status_cb, force=True)
    print()
    if results:
        ok_c   = sum(1 for r in results if r[0])
        pushed = sum(1 for r in results if r[1])
        _sep()
        print(f"  Commits made   {G}{ok_c}{RST}")
        print(f"  Pushed         {G if pushed else Y}{pushed}{RST}")
        if pushed and cfg.get("github_username"):
            print(f"\n  {B}github.com/{cfg['github_username']}{RST}")
        state = core.load_state()
        state["last_run_time"] = datetime.datetime.now().strftime("%b %d %H:%M")
        core.save_state(state)
    else:
        warn("Nothing committed — already done today or skip-day")
    _pause()

def menu_start():
    _header("Start Scheduler")
    started = core.start_scheduler(status_cb=status_cb)
    if started: ok("Scheduler running — commits daily automatically")
    else: warn("Already running")
    _pause()

def menu_stop():
    _header("Stop Scheduler")
    core.stop_scheduler(); ok("Stopped")
    _pause()

def menu_status():
    _clr(); _header("Status")
    cfg   = core.load_config()
    state = core.load_state()
    today = datetime.date.today().isoformat()
    def t(v): return f"{G}yes{RST}" if v else f"{R}no{RST}"
    print(f"  {'Git installed':<22} {t(core.check_git())}")
    print(f"  {'Internet':<22} {t(core.check_internet())}")
    print(f"  {'Scheduler running':<22} {t(core.is_running())}")
    print(f"  {'Automation on':<22} {t(cfg.get('enabled',True))}")
    ai_key = cfg.get("anthropic_api_key","") or cfg.get("groq_api_key","") or cfg.get("gemini_api_key","")
    print(f"  {'AI engine':<22} {t(cfg.get('ai_enabled') and bool(ai_key))}")
    print(f"  {'Total commits':<22} {C}{core.total_commits()}{RST}")
    repos = cfg.get("repos",[])
    if repos:
        print(); _sep()
        print(f"  {BOLD}Repositories{RST}"); _sep()
        for rp in repos:
            done   = state.get(f"last_{rp}") == today
            remote = core.has_remote(rp) if Path(rp).exists() else False
            print(f"\n  {C}{Path(rp).name}{RST}  {DIM}{rp}{RST}")
            print(f"    {'Remote set':<18} {t(remote)}")
            print(f"    {'Committed today':<18} {t(done)}")
            print(f"    {'Last':<18} {Y}{state.get(f'last_{rp}','Never')}{RST}")
    else:
        print(); warn("No repos configured")
    print(); _pause()

def menu_setup_repos():
    _header("Setup Repositories")
    cfg = core.load_config()
    cur = cfg.get("github_username","")
    u = input(f"  GitHub username [{cur}]: ").strip() or cur
    cfg["github_username"] = u
    print(f"\n  {BOLD}Commit window (24h){RST}")
    try:
        lo = input(f"  Start hour [{cfg['commit_hour_min']}]: ").strip()
        hi = input(f"  End hour   [{cfg['commit_hour_max']}]: ").strip()
        if lo: cfg["commit_hour_min"] = int(lo)
        if hi: cfg["commit_hour_max"] = int(hi)
    except ValueError: warn("Keeping current hours")
    print(f"\n  {BOLD}Add repo paths{RST}  {DIM}(empty line to stop){RST}\n")
    while True:
        p = input("  Path: ").strip().strip('"')
        if not p: break
        if p in cfg["repos"]: warn("Already added"); continue
        cfg["repos"].append(p)
        try: core.init_repo(p); ok(f"Added: {p}")
        except Exception as e: err(str(e))
    core.save_config(cfg)
    ok("Saved")
    _pause()

def menu_git_remote():
    _header("Git Remote Setup — Connect to GitHub")
    cfg   = core.load_config()
    repos = cfg.get("repos",[])
    if not repos:
        err("Add a repo first (option 5)"); _pause(); return

    print(f"  {DIM}This connects your local folder to GitHub so commits get pushed online.{RST}\n")
    print(f"  {BOLD}Select repo:{RST}\n")
    for i,rp in enumerate(repos,1):
        has = core.has_remote(rp)
        icon = f"{G}(remote OK){RST}" if has else f"{Y}(no remote){RST}"
        print(f"  [{i}] {Path(rp).name}  {icon}  {DIM}{rp}{RST}")
    print()
    try:
        idx  = int(input(f"  Choose [1-{len(repos)}]: ").strip()) - 1
        rpath = repos[idx]
    except (ValueError,IndexError):
        err("Invalid"); _pause(); return

    print(f"\n  {BOLD}GitHub Personal Access Token{RST}")
    print(f"  {DIM}Get one: github.com -> Settings -> Developer settings")
    print(f"            -> Personal access tokens -> Tokens (classic)")
    print(f"  Tick: repo (full control) -> Generate token{RST}\n")
    token = input("  Token (ghp_...): ").strip()
    if not token: err("Token required"); _pause(); return

    name = Path(rpath).name
    user = cfg.get("github_username","")
    if not user:
        user = input("  GitHub username: ").strip()
        cfg["github_username"] = user
        core.save_config(cfg)

    repo_name = input(f"  GitHub repo name [{name}]: ").strip() or name
    url = f"https://{token}@github.com/{user}/{repo_name}.git"

    print(); info("Configuring remote...")
    core._run(["git","remote","remove","origin"], cwd=rpath)
    code,_,emsg = core._run(["git","remote","add","origin",url], cwd=rpath)
    if code != 0: err(f"Remote add failed: {emsg}"); _pause(); return
    ok("Remote added")

    # ensure at least one commit
    code2,out2,_ = core._run(["git","log","--oneline","-1"], cwd=rpath)
    if code2 != 0 or not out2:
        info("Creating initial commit...")
        rdme = Path(rpath)/"README.md"
        if not rdme.exists():
            rdme.write_text(f"# {repo_name}\n\nPersonal dev notes.\n",encoding="utf-8")
        core._run(["git","add","-A"],cwd=rpath)
        core._run(["git","commit","-m","Initial commit"],cwd=rpath)

    core._run(["git","branch","-M","main"],cwd=rpath)
    info("Pushing to GitHub...")
    code3,_,e3 = core._run(["git","push","-u","origin","main"],cwd=rpath)
    if code3 == 0:
        ok(f"Done! github.com/{user}/{repo_name}")
    else:
        err(f"Push failed: {e3}")
        warn("Check: token has 'repo' scope, repo exists on GitHub as empty (no README)")
    _pause()

def menu_startup():
    _header("Register Auto-Startup")
    import platform
    sys_name = "Termux" if "com.termux" in os.environ.get("PREFIX","") else platform.system()
    print(f"  Platform: {BOLD}{sys_name}{RST}\n")
    print(f"  {DIM}After this, DevPulse starts automatically every time your PC turns on.")
    print(f"  You never need to run it manually.{RST}\n")
    ans = input("  Register now? [Y/n]: ").strip().lower()
    if ans == "n": info("Skipped"); _pause(); return
    s, msg = core.register_startup()
    (ok if s else err)(msg)
    if s: print(f"\n  {DIM}Restart your PC to activate.{RST}")
    _pause()

def menu_ai_settings():
    _header("AI Settings")
    cfg = core.load_config()
    print(f"  {DIM}AI generates smarter, non-repetitive commit content.")
    print(f"  All options below have a free tier.{RST}\n")
    print(f"  [1] {G}Groq{RST}       Free. Fast. console.groq.com  (recommended)")
    print(f"  [2] {B}Gemini{RST}     Free tier. aistudio.google.com/apikey")
    print(f"  [3] {C}Anthropic{RST}  Paid. console.anthropic.com")
    print(f"  [4] {DIM}Disable AI{RST} — built-in library (always works, no key)")
    print()
    ch = input("  Choose [1-4]: ").strip()
    if ch == "4":
        cfg["ai_enabled"] = False
        cfg["groq_api_key"] = cfg["gemini_api_key"] = cfg["anthropic_api_key"] = ""
        core.save_config(cfg)
        ok("AI off — built-in library active. Works great.")
        _pause(); return
    pmap = {
        "1": ("groq",      "Groq",      "groq_api_key",      "gsk_"),
        "2": ("gemini",    "Gemini",    "gemini_api_key",    "AIza"),
        "3": ("anthropic", "Anthropic", "anthropic_api_key", "sk-ant"),
    }
    if ch not in pmap: err("Invalid"); _pause(); return
    pid, pname, kfield, prefix = pmap[ch]
    print(f"\n  {BOLD}{pname} API Key{RST}  {DIM}(starts with {prefix}...){RST}")
    key = input("  Paste key: ").strip()
    if not key: err("No key entered"); _pause(); return
    cfg["ai_provider"] = pid
    cfg[kfield]        = key
    cfg["ai_enabled"]  = True
    core.save_config(cfg)
    ok(f"{pname} AI enabled")
    _pause()

def menu_logs():
    _header("Activity Log")
    lines = core.get_log_lines(60)
    if not lines: info("No logs yet"); _pause(); return
    for line in lines:
        if "[ERROR]" in line or "[WARNING]" in line: print(f"  {Y}{line}{RST}")
        elif "Committed" in line or "Push" in line:  print(f"  {G}{line}{RST}")
        else:                                         print(f"  {DIM}{line}{RST}")
    print(); _pause()

# ─── Entry point ──────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(prog="devpulse")
    sub = parser.add_subparsers(dest="cmd")
    pr = sub.add_parser("run"); pr.add_argument("--force",action="store_true")
    ps = sub.add_parser("start"); ps.add_argument("--silent",action="store_true")
    sub.add_parser("stop"); sub.add_parser("status")
    psu = sub.add_parser("startup"); psu.add_argument("action",choices=["add","remove"],nargs="?")
    pl = sub.add_parser("logs"); pl.add_argument("-n",type=int,default=40)
    args = parser.parse_args()

    if args.cmd == "run":
        results = core.run_automation(status_cb=status_cb, force=getattr(args,"force",False))
        print(f"  Done — {sum(1 for r in results if r[0])} commit(s)"); return
    if args.cmd == "start":
        if getattr(args,"silent",False):
            core.start_scheduler()
            try:
                while True: time.sleep(60)
            except KeyboardInterrupt: pass
        else:
            core.start_scheduler(status_cb=status_cb); ok("Scheduler started")
        return
    if args.cmd == "stop":    core.stop_scheduler(); ok("Stopped"); return
    if args.cmd == "status":  menu_status(); return
    if args.cmd == "startup":
        a = getattr(args,"action",None) or "add"
        s,m = (core.register_startup() if a=="add" else core.unregister_startup())
        (ok if s else err)(m); return
    if args.cmd == "logs":    menu_logs(); return

    try: main_menu()
    except KeyboardInterrupt: print(f"\n  {DIM}Exited.{RST}\n")

if __name__ == "__main__":
    main()
