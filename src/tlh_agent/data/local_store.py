"""Local JSON storage for TLH Agent state."""

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4


def _json_serializer(obj: Any) -> Any:
    """JSON serializer for non-standard types."""
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _parse_date(value: str | None) -> date | None:
    """Parse ISO date string to date."""
    if value is None:
        return None
    return date.fromisoformat(value)


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string to datetime."""
    if value is None:
        return None
    return datetime.fromisoformat(value)


@dataclass
class WashSaleRestriction:
    """Wash sale restriction record."""

    id: str
    ticker: str
    shares_sold: Decimal
    sale_price: Decimal
    sale_date: date
    restriction_end: date
    rebuy_status: str = "pending"  # pending, completed, skipped
    rebuy_date: date | None = None
    rebuy_price: Decimal | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "WashSaleRestriction":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            ticker=data["ticker"],
            shares_sold=Decimal(data["shares_sold"]),
            sale_price=Decimal(data["sale_price"]),
            sale_date=date.fromisoformat(data["sale_date"]),
            restriction_end=date.fromisoformat(data["restriction_end"]),
            rebuy_status=data.get("rebuy_status", "pending"),
            rebuy_date=_parse_date(data.get("rebuy_date")),
            rebuy_price=Decimal(data["rebuy_price"]) if data.get("rebuy_price") else None,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "shares_sold": str(self.shares_sold),
            "sale_price": str(self.sale_price),
            "sale_date": self.sale_date.isoformat(),
            "restriction_end": self.restriction_end.isoformat(),
            "rebuy_status": self.rebuy_status,
            "rebuy_date": self.rebuy_date.isoformat() if self.rebuy_date else None,
            "rebuy_price": str(self.rebuy_price) if self.rebuy_price else None,
        }

    @property
    def days_remaining(self) -> int:
        """Days until restriction ends."""
        delta = self.restriction_end - date.today()
        return max(0, delta.days)

    @property
    def is_active(self) -> bool:
        """Whether restriction is still active."""
        return date.today() <= self.restriction_end


@dataclass
class LossLedgerYear:
    """Loss ledger for a single year."""

    short_term_losses: Decimal = field(default_factory=lambda: Decimal("0"))
    long_term_losses: Decimal = field(default_factory=lambda: Decimal("0"))
    used_against_gains: Decimal = field(default_factory=lambda: Decimal("0"))
    carryforward: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def total_losses(self) -> Decimal:
        """Total losses for the year."""
        return self.short_term_losses + self.long_term_losses

    @classmethod
    def from_dict(cls, data: dict) -> "LossLedgerYear":
        """Create from dictionary."""
        return cls(
            short_term_losses=Decimal(data.get("short_term_losses", "0")),
            long_term_losses=Decimal(data.get("long_term_losses", "0")),
            used_against_gains=Decimal(data.get("used_against_gains", "0")),
            carryforward=Decimal(data.get("carryforward", "0")),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "short_term_losses": str(self.short_term_losses),
            "long_term_losses": str(self.long_term_losses),
            "used_against_gains": str(self.used_against_gains),
            "carryforward": str(self.carryforward),
        }


@dataclass
class HarvestQueueItem:
    """Harvest opportunity in the queue."""

    id: str
    ticker: str
    shares: Decimal
    current_price: Decimal
    cost_basis: Decimal
    unrealized_loss: Decimal
    estimated_tax_benefit: Decimal
    status: str = "pending"  # pending, approved, rejected, executed
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: datetime | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "HarvestQueueItem":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            ticker=data["ticker"],
            shares=Decimal(data["shares"]),
            current_price=Decimal(data["current_price"]),
            cost_basis=Decimal(data["cost_basis"]),
            unrealized_loss=Decimal(data["unrealized_loss"]),
            estimated_tax_benefit=Decimal(data["estimated_tax_benefit"]),
            status=data.get("status", "pending"),
            created_at=_parse_datetime(data.get("created_at")) or datetime.now(),
            executed_at=_parse_datetime(data.get("executed_at")),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "ticker": self.ticker,
            "shares": str(self.shares),
            "current_price": str(self.current_price),
            "cost_basis": str(self.cost_basis),
            "unrealized_loss": str(self.unrealized_loss),
            "estimated_tax_benefit": str(self.estimated_tax_benefit),
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
        }


class LocalStore:
    """JSON-based local storage for TLH Agent state."""

    def __init__(self, path: Path | None = None) -> None:
        """Initialize local store.

        Args:
            path: Path to state file. Defaults to ~/.tlh-agent/state.json
        """
        if path is None:
            path = Path.home() / ".tlh-agent" / "state.json"
        self._path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        """Load state from file."""
        if self._path.exists():
            with open(self._path) as f:
                return json.load(f)
        return {
            "wash_sale_restrictions": [],
            "loss_ledger": {},
            "harvest_queue": [],
        }

    def _save(self) -> None:
        """Save state to file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, default=_json_serializer)

    # Wash Sale Restrictions

    def get_restrictions(self) -> list[WashSaleRestriction]:
        """Get all wash sale restrictions."""
        return [
            WashSaleRestriction.from_dict(r) for r in self._data.get("wash_sale_restrictions", [])
        ]

    def get_active_restrictions(self) -> list[WashSaleRestriction]:
        """Get only active wash sale restrictions."""
        return [r for r in self.get_restrictions() if r.is_active]

    def get_restriction_by_ticker(self, ticker: str) -> WashSaleRestriction | None:
        """Get active restriction for a ticker."""
        for r in self.get_active_restrictions():
            if r.ticker == ticker:
                return r
        return None

    def add_restriction(self, restriction: WashSaleRestriction) -> None:
        """Add a new wash sale restriction."""
        self._data["wash_sale_restrictions"].append(restriction.to_dict())
        self._save()

    def update_restriction(self, restriction: WashSaleRestriction) -> None:
        """Update an existing restriction."""
        restrictions = self._data["wash_sale_restrictions"]
        for i, r in enumerate(restrictions):
            if r["id"] == restriction.id:
                restrictions[i] = restriction.to_dict()
                self._save()
                return
        raise ValueError(f"Restriction not found: {restriction.id}")

    def remove_restriction(self, restriction_id: str) -> None:
        """Remove a restriction by ID."""
        restrictions = self._data["wash_sale_restrictions"]
        self._data["wash_sale_restrictions"] = [
            r for r in restrictions if r["id"] != restriction_id
        ]
        self._save()

    # Loss Ledger

    def get_loss_ledger(self) -> dict[int, LossLedgerYear]:
        """Get the full loss ledger."""
        ledger = self._data.get("loss_ledger", {})
        return {int(year): LossLedgerYear.from_dict(data) for year, data in ledger.items()}

    def get_loss_ledger_year(self, year: int) -> LossLedgerYear:
        """Get loss ledger for a specific year."""
        ledger = self.get_loss_ledger()
        return ledger.get(year, LossLedgerYear())

    def update_loss_ledger_year(self, year: int, entry: LossLedgerYear) -> None:
        """Update loss ledger for a specific year."""
        if "loss_ledger" not in self._data:
            self._data["loss_ledger"] = {}
        self._data["loss_ledger"][str(year)] = entry.to_dict()
        self._save()

    # Harvest Queue

    def get_harvest_queue(self) -> list[HarvestQueueItem]:
        """Get all harvest queue items."""
        return [HarvestQueueItem.from_dict(item) for item in self._data.get("harvest_queue", [])]

    def get_pending_harvests(self) -> list[HarvestQueueItem]:
        """Get pending harvest items."""
        return [item for item in self.get_harvest_queue() if item.status == "pending"]

    def get_approved_harvests(self) -> list[HarvestQueueItem]:
        """Get approved harvest items."""
        return [item for item in self.get_harvest_queue() if item.status == "approved"]

    def add_harvest_item(self, item: HarvestQueueItem) -> None:
        """Add a new harvest queue item."""
        self._data["harvest_queue"].append(item.to_dict())
        self._save()

    def update_harvest_item(self, item: HarvestQueueItem) -> None:
        """Update an existing harvest queue item."""
        queue = self._data["harvest_queue"]
        for i, q in enumerate(queue):
            if q["id"] == item.id:
                queue[i] = item.to_dict()
                self._save()
                return
        raise ValueError(f"Harvest item not found: {item.id}")

    def remove_harvest_item(self, item_id: str) -> None:
        """Remove a harvest queue item by ID."""
        queue = self._data["harvest_queue"]
        self._data["harvest_queue"] = [q for q in queue if q["id"] != item_id]
        self._save()

    def clear_expired_harvests(self) -> int:
        """Remove expired pending harvests (older than 1 day)."""
        cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        queue = self._data["harvest_queue"]
        original_count = len(queue)

        self._data["harvest_queue"] = [
            q
            for q in queue
            if q["status"] != "pending" or _parse_datetime(q.get("created_at")) >= cutoff  # type: ignore[operator]
        ]

        if len(self._data["harvest_queue"]) != original_count:
            self._save()

        return original_count - len(self._data["harvest_queue"])

    # Utility

    def new_id(self) -> str:
        """Generate a new unique ID."""
        return str(uuid4())
