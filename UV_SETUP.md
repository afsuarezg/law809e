# Fixing Hardlink Errors with uv on Windows/OneDrive

## Problem
When running `uv venv` on Windows (especially in OneDrive folders), you may encounter hardlink errors like:
```
Error: failed to create hardlink
```

This happens because OneDrive and some network drives don't support hardlinks.

## Solutions

### Solution 1: Use `--link-mode=copy` flag (Recommended)

```powershell
# Create venv using copy mode (no hardlinks)
uv venv --link-mode=copy

# Then activate and install (also use copy mode for packages)
.\.venv\Scripts\Activate.ps1
uv pip install --link-mode=copy -r requirements.txt
uv pip install --link-mode=copy google-generativeai
```

### Solution 2: Set Environment Variable

```powershell
# Set environment variable to use copy mode
$env:UV_LINK_MODE = "copy"

# Then create venv normally (will use copy mode)
uv venv

# Activate and install
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
uv pip install google-generativeai
```

### Solution 3: Use Copy Mode Globally

Add to your PowerShell profile (`$PROFILE`):
```powershell
$env:UV_LINK_MODE = "copy"
```

Or set it permanently:
```powershell
[System.Environment]::SetEnvironmentVariable("UV_LINK_MODE", "copy", "User")
```

### Solution 4: Use uv run (No venv needed)

```powershell
# uv run automatically handles environment
uv run python -m synthetic_notices.llm_main --count 100 --valid-ratio 0.3
```

## Quick Setup Commands

```powershell
# Navigate to project
cd "c:\Users\Andres.DESKTOP-D77KM25\OneDrive - Stanford\2021 - 2025\2025-2026\AI for Legal Help\repo\law809e"

# Create venv using copy mode (no hardlinks)
uv venv --link-mode=copy

# Activate
.\.venv\Scripts\Activate.ps1

# Install dependencies (also use copy mode)
uv pip install --link-mode=copy -r requirements.txt
uv pip install --link-mode=copy google-generativeai

# Run your code
python -m synthetic_notices.llm_main --count 100 --valid-ratio 0.3
```

## Alternative: Use Standard venv

If uv continues to cause issues, use standard Python venv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install google-generativeai
```
