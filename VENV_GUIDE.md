# Virtual Environment Setup Guide

## Current Status

Your `.venv` directory exists but may be corrupted or have file locks (likely from OneDrive sync).

## Quick Solutions

### Option 1: Use Python Directly (No Activation Needed)

You can use the virtual environment Python directly without activating:

```powershell
# Install packages
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install google-generativeai

# Run scripts
.\.venv\Scripts\python.exe validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --regex

# Run modules
.\.venv\Scripts\python.exe -m synthetic_notices.llm_main --count 10 --valid-ratio 0.3 --provider openai --format json
```

### Option 2: Fix Activation Issue

If you want to activate the environment:

**Method A: Bypass Execution Policy**
```powershell
# Use the activation script directly with bypass
& .\.venv\Scripts\Activate.ps1

# Or set execution policy for current session
Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
.\.venv\Scripts\Activate.ps1
```

**Method B: Manual Environment Variables**
```powershell
$env:VIRTUAL_ENV = (Resolve-Path .venv).Path
$env:PATH = "$env:VIRTUAL_ENV\Scripts;$env:PATH"
```

### Option 3: Create New Virtual Environment

If the current `.venv` is corrupted:

1. **Close all Python processes** (check Task Manager)
2. **Pause OneDrive sync** temporarily
3. **Delete `.venv` folder** manually in File Explorer
4. **Run setup script:**
   ```powershell
   .\setup_venv.ps1
   ```

Or create with a different name:
```powershell
python -m venv venv_new
.\venv_new\Scripts\Activate.ps1
```

## Verify Installation

Check if packages are installed:
```powershell
.\.venv\Scripts\python.exe -m pip list
```

Test imports:
```powershell
.\.venv\Scripts\python.exe -c "import pydantic; print('pydantic OK')"
.\.venv\Scripts\python.exe -c "import pytesseract; print('pytesseract OK')"
.\.venv\Scripts\python.exe -c "import openai; print('openai OK')"
```

## Recommended Workflow

Since activation can be problematic with OneDrive, use direct Python calls:

```powershell
# Install packages
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# Run validation script
.\.venv\Scripts\python.exe validate_synthetic_notices.py synthetic_notices/output/LLM_generated/batch_10_notices.json --regex

# Generate synthetic notices
.\.venv\Scripts\python.exe -m synthetic_notices.llm_main --count 10 --valid-ratio 0.3 --provider openai --format json
```

## Troubleshooting

### "Access Denied" Errors
- Close all Python processes
- Pause OneDrive sync
- Try again

### "No module named 'X'" Errors
- Install missing package: `.\.venv\Scripts\python.exe -m pip install X`

### Execution Policy Errors
- Use direct Python calls instead of activation
- Or run: `Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process`
