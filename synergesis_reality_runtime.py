"""Independent runtime probes for SYN-REALITY.

These probes observe OS/process/network state without trusting executor output.

They are intentionally narrow:
- ProcessMarkerProbe searches the local process table for a caller-supplied
  correlation marker, optionally restricted to allowed executable basenames.
- LoopbackTcpProbe verifies connectivity only to explicit loopback hosts and an
  allowed port range. It is not a general network scanner.

The probes are read-only and return RealityObservation objects.
"""
from __future__ import annotations

from dataclasses import dataclass
import socket
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence, Tuple

import psutil

from synergesis_reality import RealityObservation


@dataclass(frozen=True)
class ProcessMarkerPolicy:
    marker_parameter: str
    allowed_executable_basenames: frozenset[str]
    max_processes_scanned: int = 4096

    def __post_init__(self):
        if not self.marker_parameter.strip():
            raise ValueError("marker_parameter is required")
        if not self.allowed_executable_basenames:
            raise ValueError("allowed_executable_basenames cannot be empty")
        if self.max_processes_scanned < 1:
            raise ValueError("max_processes_scanned must be >= 1")


class ProcessMarkerProbe:
    """Observe whether a live local process carries a unique marker argument."""

    def __init__(
        self,
        *,
        observer_id: str,
        policy: ProcessMarkerPolicy,
    ):
        if not observer_id.strip():
            raise ValueError("observer_id is required")
        self.observer_id = observer_id
        self.policy = policy

    @staticmethod
    def _basename(value: Optional[str]) -> str:
        return Path(value or "").name

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        marker = parameters.get(self.policy.marker_parameter)
        if not isinstance(marker, str) or not marker.strip():
            raise ValueError("process marker parameter must be a non-empty string")

        matches = []
        scanned = 0
        for process in psutil.process_iter(
            attrs=["pid", "name", "exe", "cmdline", "status", "create_time"]
        ):
            scanned += 1
            if scanned > self.policy.max_processes_scanned:
                break
            try:
                info = process.info
                exe_base = self._basename(info.get("exe")) or str(info.get("name") or "")
                if exe_base not in self.policy.allowed_executable_basenames:
                    continue
                cmdline = tuple(str(x) for x in (info.get("cmdline") or ()))
                if marker not in cmdline:
                    continue
                matches.append({
                    "pid": int(info["pid"]),
                    "exe_basename": exe_base,
                    "status": info.get("status"),
                    "create_time": info.get("create_time"),
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        facts = {
            "marker_found": bool(matches),
            "match_count": len(matches),
            "matches": matches,
            "processes_scanned": scanned,
        }
        return (
            RealityObservation.create(
                observer_id=self.observer_id,
                channel="process_table",
                resource=resource,
                facts=facts,
            ),
        )


@dataclass(frozen=True)
class LoopbackTcpPolicy:
    host_parameter: str
    port_parameter: str
    allowed_hosts: frozenset[str]
    min_port: int
    max_port: int
    timeout_seconds: float

    def __post_init__(self):
        if not self.host_parameter.strip() or not self.port_parameter.strip():
            raise ValueError("host_parameter and port_parameter are required")
        allowed_loopback = {"127.0.0.1", "::1", "localhost"}
        if not self.allowed_hosts or not self.allowed_hosts <= allowed_loopback:
            raise ValueError("LoopbackTcpPolicy only allows loopback hosts")
        if not (1 <= self.min_port <= self.max_port <= 65535):
            raise ValueError("invalid TCP port range")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be > 0")


class LoopbackTcpProbe:
    """Verify that a configured local TCP endpoint is accepting connections."""

    def __init__(
        self,
        *,
        observer_id: str,
        policy: LoopbackTcpPolicy,
    ):
        if not observer_id.strip():
            raise ValueError("observer_id is required")
        self.observer_id = observer_id
        self.policy = policy

    def _target(
        self,
        parameters: Mapping[str, Any],
    ) -> tuple[str, int]:
        host = parameters.get(self.policy.host_parameter)
        port = parameters.get(self.policy.port_parameter)
        if not isinstance(host, str) or host not in self.policy.allowed_hosts:
            raise ValueError("TCP reality probe host is not allowlisted loopback")
        if isinstance(port, bool) or not isinstance(port, int):
            raise ValueError("TCP reality probe port must be an integer")
        if not (self.policy.min_port <= port <= self.policy.max_port):
            raise ValueError("TCP reality probe port is outside allowed range")
        return host, port

    def observe(
        self,
        *,
        action_type: str,
        resource: str,
        parameters: Mapping[str, Any],
    ) -> Sequence[RealityObservation]:
        host, port = self._target(parameters)
        connected = False
        peer = None
        error_type = None
        try:
            with socket.create_connection(
                (host, port),
                timeout=self.policy.timeout_seconds,
            ) as sock:
                connected = True
                peer = list(sock.getpeername())
        except OSError as exc:
            error_type = type(exc).__name__

        return (
            RealityObservation.create(
                observer_id=self.observer_id,
                channel="tcp_connectivity",
                resource=resource,
                facts={
                    "connected": connected,
                    "host": host,
                    "port": port,
                    "peer": peer,
                    "error_type": error_type,
                },
            ),
        )
