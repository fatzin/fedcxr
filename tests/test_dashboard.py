"""API do dashboard, servida sobre runs_final/, e o protocolo da proteção térmica que ele lê."""
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from dashboard import server
from fedcxr.grids import PAPER_GRIDS
from scripts import launch, thermal_guard

RUNS_FINAL = Path(__file__).resolve().parents[1] / "runs_final"


@pytest.fixture(scope="module")
def base_url():
    handler = type("H", (server.Handler,), {"runs_dir": RUNS_FINAL})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def get(url):
    with urllib.request.urlopen(url) as r:
        return json.loads(r.read())


RUN_KEYS = {"name", "group", "status", "method", "het", "seed", "lr", "max_rounds", "pid", "gpu_bus", "gpu_name",
            "started", "n_train", "kl_mean", "clients", "dataset", "rows", "client_stats", "summary", "updated"}


def test_state_lists_every_run_of_the_paper(base_url):
    state = get(f"{base_url}/api/state")
    assert set(state) == {"time", "gpus", "procs", "gpu_hist", "grids", "guard", "host", "stalled_after"}
    assert state["stalled_after"] == server.RUNNING_WINDOW
    grids = state["grids"]
    assert sorted(g["grid"] for g in grids) == sorted(PAPER_GRIDS) and sum(len(g["runs"]) for g in grids) == 199
    assert all(g["expected"] == len(g["runs"]) for g in grids)
    run = grids[0]["runs"][0]
    assert set(run) == RUN_KEYS and run["status"] == "done" and set(run["rows"][0]) == set(server.ROW_KEYS)


def test_run_returns_every_round_in_full(base_url):
    name = "scaffold-cweighted_dir0.1_s0"
    body = get(f"{base_url}/api/run?grid=scaffold_var&run={name}")
    lines = (RUNS_FINAL / "scaffold_var" / name / "rounds.jsonl").read_text().splitlines()
    assert body["grid"] == "scaffold_var" and body["name"] == name
    assert body["rows"] == [json.loads(line) for line in lines]
    assert all("client_stats" in r for r in body["rows"])


@pytest.mark.parametrize("query", ["grid=h2&run=nao-existe", "grid=nada&run=x", "grid=h2", "grid=..&run=h2",
                                   "grid=h2&run=../h3/fedavg-full_iid_sev0.0_s0", "grid=h2&run=_logs",
                                   "grid=h2&run=summary.json"])
def test_run_rejects_unknown_or_unsafe_names(base_url, query):
    with pytest.raises(urllib.error.HTTPError) as e:
        get(f"{base_url}/api/run?{query}")
    assert e.value.code == 404


def test_launch_info_comes_from_the_python_modules(base_url):
    info = get(f"{base_url}/api/launch-info")
    runs = {g["name"]: g["runs"] for g in info["grids"]}
    assert runs["smoke"] == 8 and info["paper"]["runs"] == 199 == sum(runs[g] for g in info["paper"]["grids"])
    guard = thermal_guard.parser().parse_args([])
    assert info["guard_defaults"] == {"hot": guard.hot, "cool": guard.cool}
    assert info["modal"] == {"volume": launch.MODAL_VOLUME, "default_k": launch.MODAL_DEFAULT_K}
    assert info["local"] == {"default_k": launch.LOCAL_DEFAULT_K}
    assert info["colab"] == {"url": launch.COLAB_NOTEBOOK_URL, "default_k": launch.COLAB_DEFAULT_K,
                             "max_runs": launch.COLAB_MAX_RUNS}


def test_dashboard_reads_what_the_guard_logs(tmp_path, monkeypatch):
    monkeypatch.setattr(thermal_guard, "LOG_FILE", tmp_path / "guard.log")
    monkeypatch.setattr(thermal_guard, "PID_FILE", tmp_path / "guard.pid")
    thermal_guard.log("GPU 1 a 91 °C: treino 123 pausado")
    thermal_guard.log("GPU 1 a 70 °C: treino 123 retomado")
    thermal_guard.log("erro: nvidia-smi falhou")
    events = thermal_guard.read_state()["events"]
    assert [(e["kind"], e["gpu"], e["temp"]) for e in events] == [("pause", 1, 91.0), ("resume", 1, 70.0),
                                                                    ("error", None, None)]


@pytest.mark.parametrize("path,ctype", [("/style.css", "text/css"), ("/app/main.js", "text/javascript"),
                                        ("/vendor/preact.module.js", "text/javascript"),
                                        ("/vendor/chart.umd.js", "text/javascript")])
def test_interface_files_are_served(base_url, path, ctype):
    with urllib.request.urlopen(base_url + path) as r:
        assert r.status == 200 and r.headers["Content-Type"].startswith(ctype) and r.read()


def test_index_imports_only_local_modules(base_url):
    with urllib.request.urlopen(base_url + "/") as r:
        html = r.read().decode()
    assert '<script type="importmap">' in html and "cdn.jsdelivr" not in html
    for src in ("/style.css", "/app/main.js", "/vendor/chart.umd.js", "/vendor/signals-core.module.js"):
        assert src in html


@pytest.mark.parametrize("path", ["/server.py", "/app/../server.py", "/vendor/%2e%2e/server.py", "/app/..%2fserver.py",
                                  "/vendor/..%2f..%2fREADME.md", "/app/%2e%2e%2f%2e%2e%2fpyproject.toml", "/app",
                                  "/app/", "/vendor/README.md", "/vendor/licenses/htm.LICENSE", "/app//main.js",
                                  "/style.css/..", "/app\\..\\server.py", "/tests/test_dashboard.py"])
def test_static_route_rejects_traversal_and_other_files(base_url, path):
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(base_url + path)
    assert e.value.code == 404
