# Runs the remaining v2 pipeline unattended: waits for the detectors, calibrates, waits for the federated runs to
# finish (so that the main city runs and the timing measurements get the whole CPU), then main, trace, twin, scal and
# the post-quantum benchmark. Each step is resumable.
import json, os, subprocess, sys, time

CODE = r"E:\A-PQZTO_work\code"
RES = r"E:\A-PQZTO_work\results"
env = dict(os.environ, PYTHONIOENCODING="utf-8")


def log(msg):
    with open(os.path.join(RES, "orchestrate_v2.log"), "a") as f:
        f.write(time.strftime("%H:%M:%S ") + msg + "\n")


def step(args, name):
    log("start " + name)
    with open(os.path.join(RES, f"{name}_log.txt"), "a") as out:
        r = subprocess.run([sys.executable] + args, cwd=CODE, stdout=out, stderr=subprocess.STDOUT, env=env)
    log(f"end {name} rc={r.returncode}")
    return r.returncode


def fl_done():
    p = os.path.join(RES, "fl", "fl_runs_v2.jsonl")
    if not os.path.exists(p):
        return False
    keys = set()
    for l in open(p):
        try:
            keys.add(json.loads(l)["key"])
        except Exception:
            pass
    return len(keys) >= 1560


while not all(os.path.exists(os.path.join(RES, "detectors_v2", f"ton_det_s{s}.npz")) for s in range(1, 6)):
    time.sleep(15)
step(["run_city.py", "calib", "3"], "city_calib_v2")
while not fl_done():
    time.sleep(20)
step(["run_city.py", "main", "7"], "city_main_v2")
step(["run_city.py", "trace", "7"], "city_trace_v2")
step(["run_city.py", "twin", "7"], "city_twin_v2")
step(["run_city.py", "scal", "1"], "city_scal_v2")
step(["pqc_bench.py"], "pqc_bench")
open(os.path.join(RES, "PIPELINE_V2_DONE.txt"), "w").write(time.strftime("%H:%M:%S"))
log("all done")
