import socket
import subprocess
import sys
import threading
import time
from uuid import uuid4
from pathlib import Path

import pytest

from synergesis_reality_runtime import (
    LoopbackTcpPolicy,
    LoopbackTcpProbe,
    ProcessMarkerPolicy,
    ProcessMarkerProbe,
)


def test_process_probe_finds_real_marked_process():
    # Popen's PID and the observer's PID can belong to different namespaces.
    # A unique marker plus absent/live/terminated observations proves lifecycle
    # correlation without interpreting the observer PID as a local kill target.
    marker = "syn-reality-process-test-" + uuid4().hex
    executable = str(Path(sys.executable).resolve())
    probe = ProcessMarkerProbe(
        observer_id="os:process",
        policy=ProcessMarkerPolicy(
            marker_parameter="marker",
            allowed_executable_basenames=frozenset({Path(executable).name}),
        ),
    )

    def observe(selected_probe=probe):
        return selected_probe.observe(
            action_type="process.spawn",
            resource="action:process.spawn",
            parameters={"marker": marker},
        )[0]

    assert observe().facts["marker_found"] is False
    proc = subprocess.Popen(
        [executable, "-c", "import time; time.sleep(10)", marker],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 2.0
        while True:
            observation = observe()
            if observation.facts["marker_found"] or time.monotonic() >= deadline:
                break
            time.sleep(0.02)
        assert proc.poll() is None
        assert observation.facts["marker_found"] is True
        assert observation.facts["match_count"] == 1
        match = observation.facts["matches"][0]
        assert isinstance(match["pid"], int) and match["pid"] > 0
        assert match["exe_basename"] == Path(executable).name
        denied_probe = ProcessMarkerProbe(
            observer_id="os:denied-process",
            policy=ProcessMarkerPolicy(
                marker_parameter="marker",
                allowed_executable_basenames=frozenset({"not-the-test-executable"}),
            ),
        )
        assert observe(denied_probe).facts["marker_found"] is False
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2)

    deadline = time.monotonic() + 2.0
    while True:
        stopped = observe()
        if not stopped.facts["marker_found"] or time.monotonic() >= deadline:
            break
        time.sleep(0.02)
    assert stopped.facts["marker_found"] is False


def test_process_probe_does_not_match_wrong_marker():
    probe = ProcessMarkerProbe(
        observer_id="os:process",
        policy=ProcessMarkerPolicy(
            marker_parameter="marker",
            allowed_executable_basenames=frozenset({
                Path(sys.executable).resolve().name,
            }),
        ),
    )
    observation = probe.observe(
        action_type="process.spawn",
        resource="action:process.spawn",
        parameters={"marker": "definitely-not-running-syn-marker"},
    )[0]
    assert observation.facts["marker_found"] is False


def test_process_probe_requires_explicit_allowed_executable():
    with pytest.raises(ValueError, match="cannot be empty"):
        ProcessMarkerPolicy(
            marker_parameter="marker",
            allowed_executable_basenames=frozenset(),
        )


def _free_port():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _serve_once(port, ready):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(("127.0.0.1", port))
        server.listen(1)
        ready.set()
        server.settimeout(3)
        conn, _ = server.accept()
        conn.close()
    finally:
        server.close()


def test_loopback_tcp_probe_connects_to_real_listener():
    port = _free_port()
    ready = threading.Event()
    thread = threading.Thread(
        target=_serve_once,
        args=(port, ready),
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=2)

    probe = LoopbackTcpProbe(
        observer_id="os:tcp",
        policy=LoopbackTcpPolicy(
            host_parameter="host",
            port_parameter="port",
            allowed_hosts=frozenset({"127.0.0.1"}),
            min_port=1024,
            max_port=65535,
            timeout_seconds=0.5,
        ),
    )
    observation = probe.observe(
        action_type="tcp.listen",
        resource="action:tcp.listen",
        parameters={"host": "127.0.0.1", "port": port},
    )[0]
    assert observation.facts["connected"] is True
    assert observation.facts["port"] == port
    thread.join(timeout=2)


def test_loopback_tcp_probe_reports_no_listener():
    port = _free_port()
    probe = LoopbackTcpProbe(
        observer_id="os:tcp",
        policy=LoopbackTcpPolicy(
            host_parameter="host",
            port_parameter="port",
            allowed_hosts=frozenset({"127.0.0.1"}),
            min_port=1024,
            max_port=65535,
            timeout_seconds=0.1,
        ),
    )
    observation = probe.observe(
        action_type="tcp.listen",
        resource="action:tcp.listen",
        parameters={"host": "127.0.0.1", "port": port},
    )[0]
    assert observation.facts["connected"] is False


def test_loopback_policy_rejects_non_loopback_host():
    with pytest.raises(ValueError, match="only allows loopback"):
        LoopbackTcpPolicy(
            host_parameter="host",
            port_parameter="port",
            allowed_hosts=frozenset({"8.8.8.8"}),
            min_port=1024,
            max_port=65535,
            timeout_seconds=0.1,
        )


def test_loopback_probe_rejects_out_of_range_port_before_connect():
    probe = LoopbackTcpProbe(
        observer_id="os:tcp",
        policy=LoopbackTcpPolicy(
            host_parameter="host",
            port_parameter="port",
            allowed_hosts=frozenset({"127.0.0.1"}),
            min_port=20000,
            max_port=21000,
            timeout_seconds=0.1,
        ),
    )
    with pytest.raises(ValueError, match="outside allowed range"):
        probe.observe(
            action_type="tcp.listen",
            resource="action:tcp.listen",
            parameters={"host": "127.0.0.1", "port": 19999},
        )
