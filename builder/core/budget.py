"""Budget ledger (HAR-005): reserve conservatively before a run, then
reconcile observed usage. Exhaustion blocks the next run; it never
degrades verification."""
import json
import pathlib

import yaml


class BudgetExhausted(RuntimeError):
    pass


class BudgetLedger:
    def __init__(self, budgets_path: pathlib.Path, ledger_path: pathlib.Path):
        cfg = yaml.safe_load(budgets_path.read_text())
        self.session_ceiling = cfg["session_ceiling"]
        self.day_ceiling = cfg["day_ceiling"]
        self.ledger_path = pathlib.Path(ledger_path)

    def _entries(self):
        if not self.ledger_path.exists():
            return []
        return [json.loads(x) for x in
                self.ledger_path.read_text().splitlines() if x.strip()]

    def committed(self) -> float:
        total = 0
        for e in self._entries():
            total += e.get("reconciled_cost", e["reserved_cost"])
        return total

    def reserve(self, run_id: str, worst_case_cost: float) -> None:
        if self.session_ceiling is None or self.day_ceiling is None:
            raise BudgetExhausted("ceilings unset: fail closed (G0-Q7/D-009)")
        if self.committed() + worst_case_cost > self.session_ceiling:
            raise BudgetExhausted(
                f"reservation {worst_case_cost} would exceed session ceiling "
                f"{self.session_ceiling}; task -> blocked_budget")
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps({"run_id": run_id,
                                "reserved_cost": worst_case_cost}) + "\n")

    def reconcile(self, run_id: str, observed_cost: float) -> None:
        entries = self._entries()
        for e in entries:
            if e["run_id"] == run_id and "reconciled_cost" not in e:
                e["reconciled_cost"] = observed_cost
                break
        else:
            raise RuntimeError(f"no open reservation for {run_id}")
        self.ledger_path.write_text(
            "".join(json.dumps(e) + "\n" for e in entries))
