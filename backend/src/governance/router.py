"""Governance read endpoint — exposes resolved feature flags to the frontend."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.governance.flags import resolve_all
from src.governance.schemas import FeaturesResponse

router = APIRouter()


@router.get("/features", response_model=FeaturesResponse)
def get_features(
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> FeaturesResponse:
    """Return the resolved feature-flag set so the UI can gate affordances.

    Read-only and available to any authenticated user — it only tells the
    frontend what to show. Enforcement lives on the individual endpoints.
    """
    resolved = resolve_all(db)
    return FeaturesResponse(
        flags={k: r.value for k, r in resolved.items()},
        locked={k: r.locked for k, r in resolved.items()},
    )
