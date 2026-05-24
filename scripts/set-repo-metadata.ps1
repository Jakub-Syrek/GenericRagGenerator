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
$Topics = @(
    'ai',
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

foreach ($topic in $Topics) {
    & $Gh.Source repo edit $Repo --add-topic $topic | Out-Null
}

Write-Host "Done. Verify with: gh repo view $Repo --json description,homepageUrl,repositoryTopics"
