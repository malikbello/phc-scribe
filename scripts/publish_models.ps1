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

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)

$asr = "data\private\models\asrft-20261003\asr-ft"
foreach ($lang in "yo", "pcm") {
    if (-not (Test-Path "$asr\$lang\asrft-summary.json")) {
        throw "ASR model not found at $asr\$lang (expected asrft-summary.json there). Download it from the Kaggle notebook phc-scribe-baseline v17 output (asr-ft\$lang) into that folder, then run this again."
    }
}

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
& $python -c "import huggingface_hub" 2>$null
if ($LASTEXITCODE -ne 0) { & $python -m pip install -q "huggingface_hub[hf_xet]" }
if (-not (Get-Command modal -ErrorAction SilentlyContinue)) {
    throw "The modal command is not on PATH. Activate the environment you use for Modal jobs, then run this again."
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
    modal secret create phc-scribe-hf-write "HF_TOKEN=$token" --force | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not save the Modal secret phc-scribe-hf-write." }
    modal run deploy\modal_publish.py --run natlas-qlora-v1-weighted-fs
    if ($LASTEXITCODE -ne 0) { throw "GGUF upload failed (see the error above)." }

    Write-Host "`nDone. All three repos are PRIVATE: https://huggingface.co/malikbello"
}
finally {
    $env:HF_TOKEN = $oldToken
    $token = $null
}
