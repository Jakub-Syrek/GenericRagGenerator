<#
.SYNOPSIS
    Apply the canonical About / description / topics block to the GitHub repo.

.DESCRIPTION
    Wraps `gh repo edit` so the GitHub project page carries the same
    "100% local RAG, code + docs, fully RESTful, hardenable for corp"
    pitch as the README. Idempotent — re-run any time to enforce the
    canonical metadata.

.NOTES
    Requires the GitHub CLI (https://cli.github.com) installed and
    authenticated:
        winget install GitHub.cli
        gh auth login --hostname github.com --git-protocol https --web

    Skip-the-prompt one-liner when running over SSH:
        $env:GH_TOKEN = "<personal-access-token>"
#>
[CmdletBinding()]
param(
    [string]$Repo = 'Jakub-Syrek/GenericRagGenerator'
)

$ErrorActionPreference = 'Stop'

$Gh = Get-Command gh -ErrorAction SilentlyContinue
if (-not $Gh) {
    $candidate = 'C:\Program Files\GitHub CLI\gh.exe'
    if (Test-Path $candidate) {
        $Gh = Get-Item $candidate
    }
    else {
        throw "GitHub CLI not found. winget install GitHub.cli and re-run."
    }
}

# About / description shown on the repo's top card.
$Description = 'Local-first RAG service (FastAPI + Ollama + LlamaIndex + ChromaDB). Ingest documents, repositories or multi-source projects; query via a fully RESTful API. Runs as a process, Windows service, or Docker. No cloud, no telemetry.'

# Canonical topics — keep alphabetically sorted, lower-kebab.
# GitHub caps the topic list at 20 entries.
$Topics = @(
    'bandit',
    'chromadb',
    'docker',
    'embeddings',
    'fastapi',
    'jwt',
    'llama-index',
    'llm',
    'local-first',
    'nomic-embed-text',
    'nssm',
    'ollama',
    'pre-commit',
    'python',
    'rag',
    'retrieval-augmented-generation',
    'security',
    'self-hosted',
    'vector-database',
    'windows-service'
)

$Homepage = 'https://github.com/Jakub-Syrek/GenericRagGenerator'

Write-Host "Applying metadata to $Repo..."
& $Gh.Source repo edit $Repo `
    --description $Description `
    --homepage $Homepage `
    --enable-issues=true `
    --enable-projects=false `
    --enable-wiki=false `
    --enable-discussions=true

# Sync topics to the canonical set: drop anything not on the list (GitHub
# caps the topic count at 20, so adding without removing fails fast). Run
# the removals first so the additions don't bump into the cap.
$currentJson = & $Gh.Source repo view $Repo --json repositoryTopics 2>$null
$current = @()
if ($currentJson) {
    $current = ($currentJson | ConvertFrom-Json).repositoryTopics | ForEach-Object { $_.name }
}
foreach ($topic in $current) {
    if ($topic -notin $Topics) {
        & $Gh.Source repo edit $Repo --remove-topic $topic | Out-Null
    }
}
foreach ($topic in $Topics) {
    if ($topic -notin $current) {
        & $Gh.Source repo edit $Repo --add-topic $topic | Out-Null
    }
}

Write-Host "Done. Verify with: gh repo view $Repo --json description,homepageUrl,repositoryTopics"
