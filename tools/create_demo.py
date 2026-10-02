"""Create the reproducible synthetic demo under examples/demo-bank."""
import sys
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/interview-bank/scripts"))

from demo_data import make_bundle
from ibank_core.index import rebuild_index
from ibank_core.runs import commit_run, stage_bundle
from ibank_core.storage import atomic_write, dumps, initialize, open_bank


def main():
    bank = ROOT / "examples/demo-bank"
    initialize(bank)
    with open_bank(bank) as (_, _, data):
        populated = bool(data["questions"])
    if populated:
        print("Demo already populated; retained existing data.")
        return
    bundle = make_bundle(bank / "media")
    atomic_write(bank / "demo-input.json", dumps(bundle) + "\n")
    staged = stage_bundle(bank, bundle)
    print(dumps(commit_run(bank, staged["run_id"])))
    print(dumps(rebuild_index(bank)))


if __name__ == "__main__":
    main()
