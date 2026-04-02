#Requires -Version 7
<#
.SYNOPSIS
    Deploys IntuneCD Monitor to an Azure VM.
    Images are pulled from GitHub Container Registry (ghcr.io) — public, no auth needed.
    - Creates Azure AD App Registration
    - Provisions Azure VM
    - Generates .env, docker-compose.yml, and Caddyfile on the VM
    - Pulls images and starts the stack
.USAGE
    .\deploy.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Helpers ─────────────────────────────────────────────────────────────────

function Write-Step ($msg) { Write-Host "`n▶  $msg" -ForegroundColor Cyan }
function Write-OK   ($msg) { Write-Host "   ✔  $msg" -ForegroundColor Green }
function Write-Fail ($msg) { Write-Host "`n   ✘  $msg`n" -ForegroundColor Red; exit 1 }

function Read-Input ($prompt, $default = $null) {
    $hint = if ($default) { " (default: $default)" } else { "" }
    Write-Host "  $prompt$hint : " -NoNewline -ForegroundColor White
    $value = Read-Host
    if ([string]::IsNullOrWhiteSpace($value) -and $null -ne $default) { return $default }
    if ([string]::IsNullOrWhiteSpace($value)) { Write-Fail "A value is required for: $prompt" }
    return $value.Trim()
}

function Read-Secret ($prompt) {
    Write-Host "  $prompt : " -NoNewline -ForegroundColor White
    $secure = Read-Host -AsSecureString
    return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    )
}

function Invoke-Az {
    param([string[]]$Arguments, [switch]$AllowFailure)
    $output = az @Arguments 2>&1
    if ($LASTEXITCODE -ne 0 -and -not $AllowFailure) {
        Write-Fail "az $($Arguments -join ' ') failed:`n$output"
    }
    return $output
}

function Write-TempJson ($object) {
    $path = [System.IO.Path]::GetTempFileName() + ".json"
    $object | ConvertTo-Json -Depth 10 | Set-Content $path -Encoding UTF8
    return $path
}

# ─── Preflight ────────────────────────────────────────────────────────────────

Write-Step "Checking prerequisites"
foreach ($tool in @("az", "ssh", "scp")) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Fail "Required tool not found: '$tool'"
    }
}
try { az account show | Out-Null; if ($LASTEXITCODE -ne 0) { throw } }
catch { Write-Fail "Not logged in to Azure. Run: az login" }
Write-OK "Prerequisites OK"

# ─── Gather inputs ────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════╗" -ForegroundColor DarkCyan
Write-Host "  ║   IntuneCD Monitor — Deployment Setup        ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════╝" -ForegroundColor DarkCyan
Write-Host ""

Write-Host "  [ Azure ]" -ForegroundColor DarkGray
$TenantId      = Read-Input "Azure Tenant ID"
$ResourceGroup = Read-Input "Resource group" "lab"
$Location      = Read-Input "Azure region" "swedencentral"

Write-Host ""
Write-Host "  [ VM ]" -ForegroundColor DarkGray
$VmName        = Read-Input "VM name" "intunecd-vm"
$VmSize        = Read-Input "VM size" "Standard_B2s"
$VmUser        = Read-Input "VM admin username" "azureuser"

Write-Host ""
Write-Host "  [ Images & DNS ]" -ForegroundColor DarkGray
$ImageTag      = Read-Input "Image tag" "latest"
$DnsLabel      = Read-Input "DNS label (becomes <label>.<region>.cloudapp.azure.com)" "intunecd-monitor"

Write-Host ""
Write-Host "  [ Application ]" -ForegroundColor DarkGray
$CompanyName   = Read-Input "Company name"
$AdminRole     = Read-Input "Admin role name" "intunecd_admin"
$Timezone      = Read-Input "Timezone" "Europe/Stockholm"

Write-Host ""
Write-Host "  [ Secrets ]" -ForegroundColor DarkGray
$PostgresPass  = Read-Secret "PostgreSQL password (strong, min 16 chars)"

$Hostname    = "${DnsLabel}.${Location}.cloudapp.azure.com"
$RedirectUri = "https://${Hostname}/authorized"
$RedirectUriTenants = "https://$Hostname/tenants"
$SecretKey   = -join ((33..126) | Get-Random -Count 48 | ForEach-Object { [char]$_ })
$GhcrBase    = "ghcr.io/almenscorner/intunecd-monitor"

Write-Host ""
Write-OK "App will be deployed to: https://$Hostname"
Write-OK "Images: $GhcrBase/{web,worker,beat}:$ImageTag"

# ─── Verify resource group exists ──────────────────────────────────────
try {
    $rg = Invoke-Az @("group", "show", "--name", $ResourceGroup, "--only-show-errors")
} catch {
    # If the resource group doesn't exist, prompt to create it
    Write-Host "" -ForegroundColor Yellow
    $create = Read-Input "Resource group '$ResourceGroup' not found. Create it?" "Y"
    if ($create -notin @("Y", "y")) {
        Write-Fail "Resource group is required to proceed."
    }
    try {
        Invoke-Az @("group", "create", "--name", $ResourceGroup, "--location", $Location, "--only-show-errors") | Out-Null
        Write-OK "Resource group '$ResourceGroup' created."
    } catch {
        Write-Fail "Failed to create resource group '$ResourceGroup'."
    }

}

# ─── Phase 1: Azure AD App Registration ──────────────────────────────────────

Write-Step "Creating Azure AD App Registration"

$appRoles = @(
    @{
        allowedMemberTypes = @("User"); isEnabled = $true
        displayName = "IntuneCD Admin"; value = $AdminRole
        description = "Full administrator access to IntuneCD Monitor"
        id = [System.Guid]::NewGuid().ToString()
    },
    @{
        allowedMemberTypes = @("User"); isEnabled = $true
        displayName = "IntuneCD User"; value = "intunecd_user"
        description = "Standard read access to IntuneCD Monitor"
        id = [System.Guid]::NewGuid().ToString()
    }
)

try {
    $appJson = Invoke-Az @(
        "ad", "app", "create",
        "--display-name", "IntuneCD Monitor",
        "--sign-in-audience", "AzureADMyOrg",
        "--web-redirect-uris", $RedirectUri, $RedirectUriTenants,
        "--enable-id-token-issuance", "true",
        "--only-show-errors"
    )
} catch {
    Write-Fail "Failed to create app registration. Check if an app with the same name already exists."
}

$appObj   = ($appJson -join "`n" | ConvertFrom-Json)
$ClientId = $appObj.appId
Write-OK "App registration created — Client ID: $ClientId"

Write-Host "   Waiting 20s for app registration to propagate..." -ForegroundColor DarkGray
Start-Sleep -Seconds 20

# Add Graph delegated permissions
Write-Host "   Adding API permissions..." -ForegroundColor DarkGray
$graphAppId = "00000003-0000-0000-c000-000000000000"
$permissions = @(
    "78145de6-330d-4800-a6ce-494ff2d33d07=Role"  # DeviceManagementApps.ReadWrite.All (Application)
    "9241abd9-d0e6-425a-bd4f-47ba86e767a4=Role"  # DeviceManagementConfiguration.ReadWrite.All (Application)
    "243333ab-4d21-40cb-a475-36241daa0842=Role"  # DeviceManagementManagedDevices.ReadWrite.All (Application)
    "e330c4f0-4170-414e-a55a-2f022ec2b57b=Role"  # DeviceManagementRBAC.ReadWrite.All (Application)
    "c7a5be92-2b3d-4540-8a67-c96dcaae8b43=Role"  # DeviceManagementScripts.Read.All (Application)
    "9255e99d-faf5-445e-bbf7-cb71482737c4=Role"  # DeviceManagementScripts.ReadWrite.All (Application)
    "5ac13192-7ace-4fcf-b828-1a26f28068ee=Role"  # DeviceManagementServiceConfig.ReadWrite.All (Application)
    "5b567255-7703-4780-807c-7be8301ae99b=Role"  # Group.Read.All (Application)
    "246dd0d5-5bd0-4def-940b-0421030a5b68=Role"  # Policy.Read.All (Application)
    "e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope" # User.Read (Delegated — for user login)
)
foreach ($perm in $permissions) {
    Invoke-Az @(
        "ad", "app", "permission", "add",
        "--id", $ClientId,
        "--api", $graphAppId,
        "--api-permissions", $perm,
        "--only-show-errors"
    ) | Out-Null
}
Write-OK "API permissions added"

# Add app roles
$arFile = Write-TempJson $appRoles
try {
    Invoke-Az @(
        "ad", "app", "update",
        "--id", $ClientId,
        "--app-roles", "@$arFile",
        "--only-show-errors"
    ) | Out-Null
} finally {
    Remove-Item $arFile -ErrorAction SilentlyContinue
}
Write-OK "App roles added"

Write-OK "App registration created — Client ID: $ClientId"

Write-Step "Creating service principal"
Invoke-Az @("ad", "sp", "create", "--id", $ClientId) | Out-Null
Write-Host "   Waiting 15s for propagation..." -ForegroundColor DarkGray
Start-Sleep -Seconds 15

Write-Step "Granting admin consent"
Invoke-Az @("ad", "app", "permission", "admin-consent", "--id", $ClientId) | Out-Null
Write-OK "Admin consent granted"

Write-Step "Creating client secret (2-year validity)"
$secretJson   = Invoke-Az @(
    "ad", "app", "credential", "reset",
    "--id", $ClientId,
    "--years", "2",
    "--append",
    "--only-show-errors"
)
$ClientSecret = ($secretJson -join "`n" | ConvertFrom-Json).password
Write-OK "Client secret created"

# ─── Phase 2: Provision VM ────────────────────────────────────────────────────

Write-Step "Checking for existing VM ($VmName)"
Invoke-Az @("vm", "show", "--resource-group", $ResourceGroup, "--name", $VmName) -AllowFailure | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-OK "VM already exists, skipping creation"
} else {
    Invoke-Az @(
        "vm", "create",
        "--resource-group", $ResourceGroup, "--name", $VmName,
        "--location", $Location, "--image", "Ubuntu2404",
        "--size", $VmSize, "--admin-username", $VmUser,
        "--generate-ssh-keys", "--public-ip-sku", "Standard",
        "--os-disk-size-gb", "30"
    ) | Out-Null
    Write-OK "VM created"
}

$VmIp = (Invoke-Az @(
    "vm", "show", "-d", "--resource-group", $ResourceGroup,
    "--name", $VmName, "--query", "publicIps", "-o", "tsv"
)).Trim()
Write-OK "VM public IP: $VmIp"

# ─── Phase 3: NSG Rules ───────────────────────────────────────────────────────

Write-Step "Configuring NSG rules"
$NsgName = (Invoke-Az @(
    "network", "nsg", "list", "--resource-group", $ResourceGroup,
    "--query", "[?contains(name, '$VmName')].name", "-o", "tsv"
)).Trim()

foreach ($port in @(80, 443)) {
    $ruleName = "Allow-$port"
    Invoke-Az @(
        "network", "nsg", "rule", "show",
        "--resource-group", $ResourceGroup, "--nsg-name", $NsgName, "--name", $ruleName
    ) -AllowFailure | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Invoke-Az @(
            "network", "nsg", "rule", "create",
            "--resource-group", $ResourceGroup, "--nsg-name", $NsgName,
            "--name", $ruleName, "--priority", [string](200 + $port),
            "--destination-port-ranges", [string]$port, "--access", "Allow", "--protocol", "Tcp"
        ) | Out-Null
    }
    Write-OK "Port $port open"
}

$MyIp = (Invoke-RestMethod "https://api.ipify.org").Trim()
Invoke-Az @(
    "network", "nsg", "rule", "update",
    "--resource-group", $ResourceGroup, "--nsg-name", $NsgName,
    "--name", "default-allow-ssh", "--source-address-prefixes", "$MyIp/32"
) | Out-Null
Write-OK "SSH locked to $MyIp/32"

# ─── Phase 4: DNS Label ───────────────────────────────────────────────────────

Write-Step "Setting DNS label"
$PipName = (Invoke-Az @(
    "network", "public-ip", "list", "--resource-group", $ResourceGroup,
    "--query", "[?contains(name, '$VmName')].name", "-o", "tsv"
)).Trim()
Invoke-Az @(
    "network", "public-ip", "update",
    "--resource-group", $ResourceGroup, "--name", $PipName, "--dns-name", $DnsLabel
) | Out-Null
Write-OK "https://$Hostname"

# ─── Phase 5: Install Docker ──────────────────────────────────────────────────

Write-Step "Installing Docker on VM"
$setupScript = @'
#!/bin/bash
set -e
if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker $USER
else
  echo "Docker already present"
fi
'@
$setupFile = [System.IO.Path]::GetTempFileName()
Set-Content $setupFile $setupScript -Encoding UTF8
scp -o StrictHostKeyChecking=no $setupFile "${VmUser}@${VmIp}:/tmp/setup.sh"
ssh -o StrictHostKeyChecking=no "${VmUser}@${VmIp}" "bash /tmp/setup.sh"
Remove-Item $setupFile
Write-OK "Docker ready"

# ─── Phase 6: Generate files ──────────────────────────────────────────────────

Write-Step "Generating configuration files"

$envContent = @"
# Generated by deploy.ps1 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
# Do not commit this file to source control.

SECRET_KEY=$SecretKey
AZURE_CLIENT_ID=$ClientId
AZURE_CLIENT_SECRET=$ClientSecret
AZURE_TENANT_ID=$TenantId
COMPANY_NAME=$CompanyName
SERVER_NAME=$Hostname
ADMIN_ROLE=$AdminRole
SCOPE='[]'
REDIRECT_PATH="/authorized"
DOCUMENTATION_FILE_NAME="documentation.html"
BEAT_DB_URI=""
TIMEZONE="$Timezone"
DOCUMENTATION_MAX_LENGTH="200"
DATABASE_URL=postgresql://postgres:${PostgresPass}@db:5432/intunecd
POSTGRES_PASSWORD="$PostgresPass"
FORWARDED_ALLOW_IPS=*
HTTPS_ONLY=true
"@

$composeContent = @"
services:

  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: `${POSTGRES_PASSWORD}
      POSTGRES_DB: intunecd
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  web:
    image: ${GhcrBase}/web:${ImageTag}
    restart: unless-stopped
    entrypoint: ./server-entrypoint.sh
    expose:
      - 8080
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    image: ${GhcrBase}/worker:${ImageTag}
    restart: unless-stopped
    entrypoint: ./worker-entrypoint.sh
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy

  beat:
    image: ${GhcrBase}/beat:${ImageTag}
    restart: unless-stopped
    entrypoint: ./beat-entrypoint.sh
    env_file: .env
    depends_on:
      redis:
        condition: service_healthy

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on:
      web:
        condition: service_healthy

volumes:
  postgres_data:
  caddy_data:
"@

$caddyContent = @"
$Hostname {
    reverse_proxy web:8080 {
        header_up Host {host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }

    header {
        X-Frame-Options SAMEORIGIN
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.jsdelivr.net cdn.socket.io cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src 'self' fonts.gstatic.com data:; img-src 'self' data:; connect-src 'self' ws: wss:;"
    }

    handle_errors 502 {
        respond "Application is starting, please wait..." 502
    }
}
"@

$tmpEnv     = [System.IO.Path]::GetTempFileName()
$tmpCompose = [System.IO.Path]::GetTempFileName()
$tmpCaddy   = [System.IO.Path]::GetTempFileName()
Set-Content $tmpEnv     $envContent     -Encoding UTF8
Set-Content $tmpCompose $composeContent -Encoding UTF8
Set-Content $tmpCaddy   $caddyContent   -Encoding UTF8
Write-OK ".env, docker-compose.yml, and Caddyfile generated"

# ─── Phase 7: Copy files and start stack ─────────────────────────────────────

Write-Step "Copying files to VM"

$envLeaf     = Split-Path $tmpEnv     -Leaf
$composeLeaf = Split-Path $tmpCompose -Leaf
$caddyLeaf   = Split-Path $tmpCaddy   -Leaf

ssh  -o StrictHostKeyChecking=no "${VmUser}@${VmIp}" "mkdir -p ~/intunecd"
scp  -o StrictHostKeyChecking=no $tmpEnv     "${VmUser}@${VmIp}:/tmp/$envLeaf"
scp  -o StrictHostKeyChecking=no $tmpCompose "${VmUser}@${VmIp}:/tmp/$composeLeaf"
scp  -o StrictHostKeyChecking=no $tmpCaddy   "${VmUser}@${VmIp}:/tmp/$caddyLeaf"

ssh -o StrictHostKeyChecking=no "${VmUser}@${VmIp}" @"
mv /tmp/$envLeaf     ~/intunecd/.env
mv /tmp/$composeLeaf ~/intunecd/docker-compose.yml
mv /tmp/$caddyLeaf   ~/intunecd/Caddyfile
chmod 600 ~/intunecd/.env
"@

Remove-Item $tmpEnv, $tmpCompose, $tmpCaddy -ErrorAction SilentlyContinue
Write-OK "Files in place (.env locked to owner only)"

Write-Step "Pulling images and starting stack"
ssh -o StrictHostKeyChecking=no "${VmUser}@${VmIp}" @"
set -e
cd ~/intunecd
echo "Pulling images from ghcr.io (public — no login needed)..."
docker compose pull
echo ""
echo "Starting services..."
docker compose up -d
echo ""
docker compose ps
"@

Write-OK "Stack started"

# ─── Done ─────────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "  ║  Deployment complete!                                    ║" -ForegroundColor Green
Write-Host "  ╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "  App URL     : https://$Hostname" -ForegroundColor White
Write-Host "  SSH         : ssh ${VmUser}@${VmIp}" -ForegroundColor White
Write-Host "  Client ID   : $ClientId" -ForegroundColor White
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor Yellow
Write-Host "  1. Entra ID > App registrations > IntuneCD Monitor" -ForegroundColor Yellow
Write-Host "     > Enterprise application > Users and groups" -ForegroundColor Yellow
Write-Host "     Assign users the '$AdminRole' or 'intunecd_user' app role" -ForegroundColor Yellow
Write-Host ""
Write-Host "  2. Wait ~60s for Caddy to get the TLS cert, then open:" -ForegroundColor Yellow
Write-Host "     https://$Hostname" -ForegroundColor Yellow
Write-Host ""
Write-Host "  To update after a new image release:" -ForegroundColor DarkGray
Write-Host "  ssh ${VmUser}@${VmIp} 'cd ~/intunecd && docker compose pull && docker compose up -d'" -ForegroundColor DarkGray
Write-Host ""