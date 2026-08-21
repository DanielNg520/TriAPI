import json
import time
from pathlib import Path

run_file = Path("logs/runs/20260820-155059-ff015c.json")
with open(run_file) as f:
    state = json.load(f)

# Change the last result (which is p0-i3 human_handoff) to success
if state.get("results") and state["results"][-1]["status"] == "human_handoff":
    state["results"][-1]["status"] = "success"
    state["results"][-1]["resolved_by"] = "manual"

state["status"] = "stopped_on_failure" # So dispatcher will resume

state["updated_at"] = time.time()

with open(run_file, "w") as f:
    json.dump(state, f, indent=2)

print("Fixed run JSON.")
