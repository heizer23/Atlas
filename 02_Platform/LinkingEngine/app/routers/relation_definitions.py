"""
LinkingEngine — relation definitions router.

Endpoints:
  GET /linking/relation-definitions

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from fastapi import APIRouter

from app.models import GetRelationDefinitionsResponse
from app.service import LinkService

router = APIRouter()
_service = LinkService()


@router.get("/linking/relation-definitions", response_model=GetRelationDefinitionsResponse)
def get_relation_definitions(active_only: bool = True):
    """
    Return canonical relation definitions.
    Used by UI for autocomplete suggestions and client-side validation hints.
    """
    defs = _service.get_relation_definitions(active_only=active_only)
    return GetRelationDefinitionsResponse(relation_definitions=defs)
