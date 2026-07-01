#!/usr/bin/env bash
# Step 64B.1 -- operator-run staging host preflight (READ-ONLY inventory).
#
# Run this ON the staging target host 10.0.1.32 as the intended staging user, then paste the
# output back. It is strictly READ-ONLY: it starts no service, installs nothing, changes no
# host configuration, and performs no production action. It prints NO password, private key,
# token, secret, or kubeconfig.
#
# Usage (on 10.0.1.32):
#   bash staging_host_preflight_operator_run.sh
set -u

line() { echo "----- $1 -----"; }

echo "===== ai-agents staging host preflight (read-only) ====="
echo "timestamp_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

line "identity"
hostname
whoami
id
groups

line "os"
uname -a
lsb_release -a 2>/dev/null || cat /etc/os-release 2>/dev/null

line "resources"
echo "nproc=$(nproc 2>/dev/null)"
free -h 2>/dev/null
df -h 2>/dev/null
uptime 2>/dev/null

line "network"
ip addr 2>/dev/null || ifconfig 2>/dev/null
ip route 2>/dev/null

line "docker"
docker --version 2>/dev/null || echo "docker: NOT INSTALLED"
docker compose version 2>/dev/null || echo "docker compose v2: NOT AVAILABLE"
systemctl is-active docker 2>/dev/null || echo "docker daemon: unknown/inactive"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || echo "docker ps: not accessible (no daemon or no group access)"

line "listening_ports"
ss -tulpn 2>/dev/null || netstat -tulpn 2>/dev/null || echo "ss/netstat: not available"

line "privilege"
if sudo -n true 2>/dev/null; then echo "sudo_nopasswd_available=true"; else echo "sudo_nopasswd_available=false"; fi
if docker info >/dev/null 2>&1; then echo "docker_group_access=true"; else echo "docker_group_access=false"; fi

echo "===== end preflight ====="
echo "NOTE: this output contains host inventory only -- no password, key, token, or secret."
