#!/usr/bin/env python3
# set_esxi_entropy_sources.py version 2.1 08-July-2026
"""
set_esxi_entropy_sources.py

Ensures esxcli entropySources (VMkernel.Boot.entropySources) = 2 on the
ESXi hosts for this vPod. Pure Python + SSH (esxcli) - no PowerCLI/pwsh
required, matching the rest of the /hol/Tools scripts.

v2.1: pre-check port 22 before attempting esxcli over SSH, so hosts that
are ping-reachable but not SSH-reachable are reported as UNREACHABLE
instead of going through a failed lsf.ssh() call.

Host list
---------
By default the host list comes from /tmp/config.ini [RESOURCES] ESXiHosts
(the same source used by Startup/ESXi.py, Startup/vSphere.py and the other
Tools/confighol* scripts). Use --hosts to override.

Behavior
--------
For each host:
  1. Read the current value via `esxcli system settings kernel list`.
  2. If already 2 -> log and skip.
  3. If not 2     -> set it via `esxcli system settings kernel set`.
     This is a boot-time kernel setting, so it only takes effect after the
     host is rebooted.
  4. If --no-reboot is NOT given, reboot the host and wait for it to come
     back online, then re-read the value to confirm it stuck.
     If --no-reboot IS given, the new value is left pending for the next
     natural reboot of the host (used during lab Shutdown, where the hosts
     are about to be powered off anyway).

This module is also imported directly by Startup/ESXi.py (reboot allowed,
since no VMs are running yet) and Shutdown/VCFshutdown-9.0.py (no reboot,
since the hosts are being shut down).

Usage
-----
    python3 set_esxi_entropy_sources.py
    python3 set_esxi_entropy_sources.py --no-reboot
    python3 set_esxi_entropy_sources.py --dry-run
    python3 set_esxi_entropy_sources.py --hosts esx-01a.site-a.vcf.lab esx-02a.site-a.vcf.lab
    python3 set_esxi_entropy_sources.py --help
"""

import argparse
import sys
import time
from dataclasses import dataclass
from typing import Optional

import lsfunctions as lsf

# ── Defaults ──────────────────────────────────────────────────────────────

SETTING_KEY      = 'entropySources'
SETTING_VALUE    = 2
ESX_USERNAME     = 'root'
REBOOT_TIMEOUT_S = 20 * 60   # 20 minutes
POLL_INTERVAL_S  = 15

# ── Result tracking ──────────────────────────────────────────────────────

@dataclass
class HostResult:
    host:          str
    initial_value: Optional[int] = None
    changed:       bool          = False
    rebooted:      bool          = False
    final_value:   Optional[int] = None
    status:        str           = 'PENDING'
    error:         Optional[str] = None


# ── config.ini helpers ────────────────────────────────────────────────────

def get_esxi_hosts_from_config() -> list:
    """
    Return the ESXi hostnames listed in [RESOURCES] ESXiHosts of config.ini
    (lsf.config), stripping the trailing ':yes|no' maintenance-mode flag.
    """
    hosts = []
    if lsf.config.has_option('RESOURCES', 'ESXiHosts'):
        for entry in lsf.config.get('RESOURCES', 'ESXiHosts').split('\n'):
            entry = entry.strip()
            if not entry or entry.startswith('#'):
                continue
            hosts.append(entry.split(':')[0])
    return hosts


# ── esxcli helpers (SSH) ──────────────────────────────────────────────────

def get_entropy_value(host: str, username: str, password: str) -> Optional[int]:
    """Return the current (Configured) entropySources value, or None on failure."""
    cmd = f'esxcli system settings kernel list -o {SETTING_KEY}'
    result = lsf.ssh(cmd, f'{username}@{host}', password)
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields and fields[0] == SETTING_KEY:
            try:
                return int(fields[2])  # Name Type Configured Runtime Default ...
            except (IndexError, ValueError):
                return None
    return None


def set_entropy_value(host: str, username: str, password: str, value: int) -> bool:
    """Set entropySources via esxcli. Returns True on success."""
    cmd = f'esxcli system settings kernel set --setting={SETTING_KEY} --value={value}'
    result = lsf.ssh(cmd, f'{username}@{host}', password)
    return result.returncode == 0


def reboot_and_wait(host: str, username: str, password: str,
                     timeout: int = REBOOT_TIMEOUT_S) -> bool:
    """Reboot host and wait for it to go offline then back online (port 22)."""
    lsf.write_output(f'  Rebooting {host}...')
    lsf.ssh('reboot', f'{username}@{host}', password)

    deadline = time.time() + timeout
    lsf.write_output(f'  Waiting for {host} to go offline...')
    while time.time() < deadline and lsf.test_tcp_port(host, 22):
        time.sleep(POLL_INTERVAL_S)

    lsf.write_output(f'  Waiting for {host} to come back online...')
    while time.time() < deadline:
        if lsf.test_tcp_port(host, 22):
            lsf.write_output(f'  {host} is back online', logfile=lsf.logfile)
            return True
        time.sleep(POLL_INTERVAL_S)

    lsf.write_output(f'  {host} did not come back online within {timeout // 60} minutes')
    return False


# ── Main orchestration (importable) ───────────────────────────────────────

def ensure_entropy_sources(hosts: list, username: str = ESX_USERNAME,
                            password: str = None, reboot: bool = True,
                            dry_run: bool = False,
                            reboot_timeout: int = REBOOT_TIMEOUT_S) -> dict:
    """
    Check and, if needed, set VMkernel.Boot.entropySources = 2 on each host.

    :param hosts: list of ESXi hostnames/FQDNs
    :param username: ESXi account to use (default root)
    :param password: ESXi root password (defaults to lsf.password from creds.txt)
    :param reboot: reboot the host to apply a changed setting immediately.
                   Pass False when the host will be rebooted/power-cycled
                   anyway (e.g. during Shutdown) - avoids a redundant reboot.
    :param dry_run: report what would change without making any changes
    :param reboot_timeout: seconds to wait for a rebooted host to return
    :return: dict of host -> HostResult
    """
    password = password or lsf.password
    results = {}

    for host in hosts:
        r = HostResult(host=host)
        try:
            if not lsf.test_tcp_port(host, 22):
                r.status = 'UNREACHABLE'
                r.error = 'Host is not reachable on port 22 (SSH)'
                lsf.write_output(f'  {host}: {r.error} - skipping')
                results[host] = r
                continue

            current = get_entropy_value(host, username, password)
            r.initial_value = current

            if current is None:
                r.status = 'ERROR'
                r.error = f'Could not read {SETTING_KEY} via esxcli'
                lsf.write_output(f'  {host}: {r.error}')
                results[host] = r
                continue

            if current == SETTING_VALUE:
                r.status = 'ALREADY_CORRECT'
                lsf.write_output(f'  {host}: {SETTING_KEY} already {SETTING_VALUE}')
                results[host] = r
                continue

            lsf.write_output(f'  {host}: {SETTING_KEY} is {current}, needs to be {SETTING_VALUE}')
            if dry_run:
                r.status = 'WOULD_CHANGE'
                results[host] = r
                continue

            if not set_entropy_value(host, username, password, SETTING_VALUE):
                r.status = 'ERROR'
                r.error = 'esxcli set command failed'
                lsf.write_output(f'  {host}: {r.error}')
                results[host] = r
                continue

            r.changed = True
            lsf.write_output(f'  {host}: {SETTING_KEY} set to {SETTING_VALUE}')

            if not reboot:
                r.status = 'PENDING_REBOOT'
                lsf.write_output(f'  {host}: change will take effect on next reboot')
                results[host] = r
                continue

            r.rebooted = reboot_and_wait(host, username, password, reboot_timeout)
            if not r.rebooted:
                r.status = 'REBOOT_TIMEOUT'
                results[host] = r
                continue

            r.final_value = get_entropy_value(host, username, password)
            r.status = 'SUCCESS' if r.final_value == SETTING_VALUE else 'VERIFY_FAILED'

        except Exception as exc:
            r.status = 'ERROR'
            r.error = str(exc)
            lsf.write_output(f'  {host}: ERROR: {exc}')

        results[host] = r

    return results


def print_summary(results: dict) -> bool:
    """Print a summary table. Returns True if every host is in a good state."""
    good_states = ('SUCCESS', 'ALREADY_CORRECT', 'PENDING_REBOOT', 'WOULD_CHANGE')
    print()
    header = f"{'Host':<40} {'Status':<16} {'Before':>6}  {'After':>5}"
    print(header)
    print('-' * len(header))
    all_ok = True
    for host, r in results.items():
        before = str(r.initial_value) if r.initial_value is not None else 'n/a'
        after = str(r.final_value) if r.final_value is not None else 'n/a'
        print(f'{host:<40} {r.status:<16} {before:>6}  {after:>5}')
        if r.error:
            print(f'  Error: {r.error}')
        if r.status not in good_states:
            all_ok = False
    print()
    return all_ok


# ── CLI ────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=f'Set esxcli {SETTING_KEY} (VMkernel.Boot.entropySources) = '
                    f'{SETTING_VALUE} on the vPod ESXi hosts.',
    )
    p.add_argument(
        '--hosts', nargs='+', default=None,
        help='ESXi host(s) to target (default: [RESOURCES] ESXiHosts from config.ini)',
    )
    p.add_argument('--username', default=ESX_USERNAME, help='ESXi username (default: root)')
    p.add_argument(
        '--no-reboot', action='store_true',
        help='Set the value but do not reboot hosts (change applies on next reboot)',
    )
    p.add_argument('--dry-run', action='store_true', help='Report only, make no changes')
    p.add_argument(
        '--reboot-timeout', type=int, default=REBOOT_TIMEOUT_S // 60, metavar='MINUTES',
        help='Minutes to wait for a rebooted host to come back (default: 20)',
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    # read /tmp/config.ini and set lsf.password from creds.txt
    lsf.init(router=False)

    hosts = args.hosts or get_esxi_hosts_from_config()
    if not hosts:
        lsf.write_output('No ESXi hosts found ([RESOURCES] ESXiHosts in config.ini is empty)')
        sys.exit(1)

    lsf.write_output(f'Checking {SETTING_KEY} on {len(hosts)} host(s): {", ".join(hosts)}')

    results = ensure_entropy_sources(
        hosts, username=args.username, reboot=not args.no_reboot,
        dry_run=args.dry_run, reboot_timeout=args.reboot_timeout * 60,
    )

    all_ok = print_summary(results)
    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
