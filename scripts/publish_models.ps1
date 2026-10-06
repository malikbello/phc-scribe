# Upload all three PHC Scribe models to PRIVATE Hugging Face repos, from the Windows laptop.
#
#   1. the Yoruba and Pidgin ASR fine-tunes (ADR-0026), uploaded from this laptop's
#      data\private\models\asrft-20261003\asr-ft by scripts/publish_asr.py;
#   2. the shipped Q4 GGUF (run C-fs), sent straight from the Modal volume to Hugging Face
#      by deploy/modal_publish.py, so the ~5 GB file never downloads here.
#
# Run from the phc-scribe folder in PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\publish_models.ps1
# It asks for the Hugging Face WRITE token without echoing it, keeps it only in this process
# and in the Modal secret "phc-scribe-hf-write", and never prints it. Every repo is created
# private; both upload scripts refuse to upload to a repo that is public.

# "Continue", not "Stop": in Windows PowerShell 5.1, "Stop" turns any stderr output of a native
# command (even a redirected one) into a terminating error. Each step checks $LASTEXITCODE instead.
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

$asr = "data\private\models\asrft-20261003\asr-ft"
foreach ($lang in "yo", "pcm") {
    if (-not (Test-Path "$asr\$lang\asrft-summary.json")) {
        throw "ASR model not found at $asr\$lang (expected asrft-summary.json there). Download it from the Kaggle notebook phc-scribe-baseline v17 output (asr-ft\$lang) into that folder, then run this again."
    }
}

$python = if (Test-Path ".venv\Scripts\python.exe") { (Resolve-Path ".venv\Scripts\python.exe").Path } else { "python" }
& $python -c "import huggingface_hub" 2>$null
if ($LASTEXITCODE -ne 0) {
    if (Get-Command uv -ErrorAction SilentlyContinue) { uv pip install -q --python $python "huggingface_hub[hf_xet]" }
    else { & $python -m pip install -q "huggingface_hub[hf_xet]" }
}
# Modal: the modal command if it is on PATH, else Modal as a module of a Python that has it,
# else install it into $python. Its sign-in (~/.modal.toml) is per user, not per environment.
$modalExe = $null
$modalPre = @()
if (Get-Command modal -ErrorAction SilentlyContinue) { $modalExe = "modal" }
else {
    foreach ($candidate in @($python, "python", "py")) {
        if (-not ((Test-Path $candidate) -or (Get-Command $candidate -ErrorAction SilentlyContinue))) { continue }
        & $candidate -c "import modal" 2>$null
        if ($LASTEXITCODE -eq 0) { $modalExe = $candidate; $modalPre = @("-m", "modal"); break }
    }
    if (-not $modalExe) {
        Write-Host "Modal is not installed; installing it into $python..."
        # .venv is made by uv (scripts/ci_local.sh) and has no pip, so install with uv when there is one
        if (Get-Command uv -ErrorAction SilentlyContinue) { uv pip install -q --python $python modal }
        else { & $python -m pip install -q modal }
        if ($LASTEXITCODE -ne 0) { throw "Could not install modal." }
        $modalExe = $python; $modalPre = @("-m", "modal")
    }
}
function Invoke-Modal { & $modalExe @modalPre @args }
if (-not ((Test-Path "$HOME\.modal.toml") -or $env:MODAL_TOKEN_ID)) {
    Write-Host "Modal is not signed in on this laptop; a browser window opens to sign in..."
    Invoke-Modal token new
    if ($LASTEXITCODE -ne 0) { throw "Modal sign-in failed." }
}

$secure = Read-Host "Paste the Hugging Face WRITE token (hidden)" -AsSecureString
$token = [System.Net.NetworkCredential]::new("", $secure).Password
if (-not $token.StartsWith("hf_")) { throw "That does not look like a Hugging Face token (it should start with hf_)." }
$oldToken = $env:HF_TOKEN
$env:HF_TOKEN = $token
try {
    Write-Host "`n[1/3] Checking the token..."
    & $python -c "from huggingface_hub import HfApi; print('  signed in to Hugging Face as', HfApi().whoami()['name'])"
    if ($LASTEXITCODE -ne 0) { throw "Hugging Face rejected the token." }

    Write-Host "`n[2/3] Uploading the Yoruba and Pidgin ASR models from this laptop (about 1 GB each)..."
    & $python scripts\publish_asr.py --models $asr
    if ($LASTEXITCODE -ne 0) { throw "ASR upload failed (see the error above)." }

    Write-Host "`n[3/3] Uploading the Q4 GGUF from Modal straight to Hugging Face (about 5 GB; runs on Modal)..."
    Invoke-Modal secret create phc-scribe-hf-write "HF_TOKEN=$token" --force | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not save the Modal secret phc-scribe-hf-write." }
    Invoke-Modal run deploy\modal_publish.py --run natlas-qlora-v1-weighted-fs
    if ($LASTEXITCODE -ne 0) { throw "GGUF upload failed (see the error above)." }

    Write-Host "`nDone. All three repos are PRIVATE: https://huggingface.co/malikbello"
}
finally {
    $env:HF_TOKEN = $oldToken
    $token = $null
}
