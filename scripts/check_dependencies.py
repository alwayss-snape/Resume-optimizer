#!/usr/bin/env python3
"""Simple dependency checker for LibreOffice and Ollama.

Usage:
  python scripts/check_dependencies.py

Exits with code 0 if checks pass, non-zero otherwise.
"""
import shutil
import subprocess
import sys

checks_ok = True

# Check for LibreOffice (soffice/libreoffice)
libre_paths = ["libreoffice", "soffice"]
found_libre = None
for cmd in libre_paths:
    if shutil.which(cmd):
        found_libre = cmd
        break

if found_libre:
    print(f"LibreOffice binary found: {found_libre}")
else:
    print("LibreOffice binary not found in PATH. PDF conversion may fail.")
    checks_ok = False

# Check for Ollama CLI
ollama_cmd = shutil.which("ollama")
if ollama_cmd:
    try:
        # Try `ollama status` as a lightweight server check (may vary by install)
        res = subprocess.run([ollama_cmd, "status"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            print("Ollama CLI found and responding (ollama status succeeded).")
        else:
            print("Ollama CLI found but `ollama status` returned non-zero. Server may be offline.")
            print(res.stdout)
            checks_ok = False
    except Exception as e:
        print(f"Ollama CLI found at {ollama_cmd} but failed to run status: {e}")
        checks_ok = False
else:
    print("Ollama CLI not found in PATH. Local LLM features will be unavailable.")
    checks_ok = False

# Summary
if not checks_ok:
    print("\nOne or more dependencies are missing or unavailable.")
    sys.exit(2)

print("\nAll runtime dependency checks passed.")
sys.exit(0)
