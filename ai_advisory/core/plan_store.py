import json
import logging
from pathlib import Path
from typing import Optional, List
from ai_advisory.api.plan_models import TradePlan

logger = logging.getLogger(__name__)

class PlanStore:
    def __init__(self, data_root: Path):
        """
        Manages purely file-based execution plans as independent JSON snapshots.
        """
        self.store_dir = data_root / "plans"
        # Ensure the target storage branch exists before write
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, plan_id: str) -> Path:
        return self.store_dir / f"{plan_id}.json"

    def save_plan(self, plan: TradePlan) -> None:
        """
        Dumps the entire Pydantic TradePlan pipeline safely to disk.
        """
        target = self._get_path(plan.plan_id)
        raw_json = plan.model_dump_json(indent=2)
        target.write_text(raw_json)
        logger.info(f"Successfully saved new TradePlan {plan.plan_id} to disk.")

    def load_plan(self, plan_id: str) -> Optional[TradePlan]:
        """
        Hydrates a raw JSON log off the disk back into a structured TradePlan model.
        Returns None if not found or corrupted.
        """
        target = self._get_path(plan_id)
        if not target.exists():
            return None
            
        try:
            raw = target.read_text()
            return TradePlan.model_validate_json(raw)
        except Exception as e:
            logger.error(f"Failed to hydrate TradePlan {plan_id} because: {str(e)}")
            return None

    def list_recent_plans(self) -> List[TradePlan]:
        """
        Scans all files and parses them into a list. 
        Note: Expensive operation, intended for low-load v0 architecture.
        """
        plans = []
        for file in self.store_dir.glob("*.json"):
            try:
                raw = file.read_text()
                plan = TradePlan.model_validate_json(raw)
                plans.append(plan)
            except Exception:
                pass
                
        # Return newest first based on instantiation stamp
        return sorted(plans, key=lambda x: x.created_at, reverse=True)
