"""
DevPulse — Python Installer
Runs after Python is confirmed. Called by START_HERE.bat / start_here.sh
Can also be run directly: python install.py
"""
from __future__ import annotations
import sys, os, subprocess, platform, shutil, urllib.request
from pathlib import Path

BASE = Path(__file__).parent
R="\033[91m";G="\033[92m";Y="\033[93m";B="\033[94m"
C="\033[96m";W="\033[97m";DIM="\033[2m";RST="\033[0m";BOLD="\033[1m"
if not sys.stdout.isatty(): R=G=Y=B=C=W=DIM=RST=BOLD=""

def ok(m):   print(f"  {G}ok{RST}  {m}")
def fail(m): print(f"  {R}!!{RST}  {m}")
def warn(m): print(f"  {Y}! {RST}  {m}")
def info(m): print(f"  {B}->{RST}  {m}")
def step(m): print(f"\n  {BOLD}{m}{RST}")

SYSTEM    = platform.system()
IS_TERMUX = "com.termux" in os.environ.get("PREFIX","")

def run(cmd, timeout=120):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout+r.stderr).strip()
    except Exception as e:
        return 1, str(e)

def check_python():
    v = sys.version_info
    if v >= (3,8):
        ok(f"Python {v.major}.{v.minor}.{v.micro}"); return True
    fail(f"Python {v.major}.{v.minor} found, need 3.8+")
    info("Download: https://python.org/downloads"); return False

def check_git():
    if shutil.which("git"):
        code,out = run(["git","--version"])
        ok(out.split("\n")[0] if code==0 else "git found"); return True
    warn("Git not found, installing...")
    if IS_TERMUX:
        code,_ = run(["pkg","install","git","-y"]); return code==0
    if SYSTEM=="Darwin":
        code,_ = run(["brew","install","git"]); return code==0
    if SYSTEM=="Linux":
        for pm,cmd in [("apt-get",["sudo","apt-get","install","-y","git"]),
                       ("dnf",["sudo","dnf","install","-y","git"]),
                       ("pacman",["sudo","pacman","-S","--noconfirm","git"])]:
            if shutil.which(pm):
                code,_ = run(cmd,180)
                if code==0: ok("Git installed"); return True
    if SYSTEM=="Windows":
        if shutil.which("winget"):
            code,_ = run(["winget","install","-e","--id","Git.Git","--silent",
                          "--accept-source-agreements","--accept-package-agreements"])
            if code==0:
                os.environ["PATH"]+=r";C:\Program Files\Git\cmd"
                ok("Git installed"); return True
        info("Downloading Git installer...")
        url  = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"
        dest = Path(os.environ.get("TEMP","."))/"git_setup.exe"
        try:
            urllib.request.urlretrieve(url, dest)
            run([str(dest),"/VERYSILENT","/NORESTART"],180)
            dest.unlink(missing_ok=True)
            os.environ["PATH"]+=r";C:\Program Files\Git\cmd"
            ok("Git installed"); return True
        except Exception as e:
            fail(f"Git download failed: {e}")
    fail("Could not auto-install Git. Get it from: https://git-scm.com")
    return False

def install_packages():
    step("Installing Python packages...")
    reqs = BASE/"requirements.txt"
    pkgs = [l.strip() for l in (reqs.read_text(encoding="utf-8") if reqs.exists() else "psutil>=5.9.0").splitlines()
            if l.strip() and not l.startswith("#")]
    for pkg in pkgs:
        name = pkg.split(">=")[0].split("==")[0].replace("-","_")
        try: __import__(name); ok(f"{name} already installed"); continue
        except ImportError: pass
        info(f"Installing {pkg}...")
        for m in [[sys.executable,"-m","pip","install",pkg,"-q"],
                  [sys.executable,"-m","pip","install",pkg,"-q","--break-system-packages"],
                  [sys.executable,"-m","pip","install",pkg,"-q","--user"]]:
            code,_ = run(m)
            if code==0:
                try: __import__(name); ok(f"{name} installed"); break
                except ImportError: pass
        else:
            warn(f"{name} could not install — continuing without it")

def setup_git_identity():
    for key in ("user.name","user.email"):
        code,val = run(["git","config","--global",key])
        if code==0 and val.strip(): ok(f"{key}: {val.strip()}"); continue
        prompt = "Your name" if "name" in key else "Your email"
        v = input(f"  {prompt}: ").strip()
        if v: run(["git","config","--global",key,v]); ok(f"{key} set")

def check_internet():
    try: urllib.request.urlopen("https://github.com",timeout=5); ok("Internet OK"); return True
    except: warn("No internet — push won't work until connected"); return False

def main():
    print(f"\n{C}  {'='*52}\n   DevPulse — Auto Installer\n   Checking everything...\n  {'='*52}{RST}\n")
    step("[1/5] Python");   check_python()
    step("[2/5] Git");      git_ok = check_git()
    step("[3/5] Packages"); install_packages()
    step("[4/5] Internet"); check_internet()
    if git_ok:
        step("[5/5] Git identity"); setup_git_identity()
    print(f"\n  {'─'*52}")
    info("Launching DevPulse interactive menu...\n")
    try:
        from cli import main_menu
        main_menu()
    except Exception as e:
        fail(f"Menu launch error: {e}")
        info("Run manually: python cli.py")

if __name__ == "__main__":
    main()
