"""
LinkingEngine — objects router.

Endpoints:
  POST /linking/objects
  GET  /linking/objects/search

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from fastapi import APIRouter

from app.models import (
    ObjectRecord,
    RegisterObjectRequest,
    SearchObjectsResponse,
)
from app.service import LinkService

router = APIRouter()
_service = LinkService()


@router.post("/linking/objects", status_code=204)
def register_object(request: RegisterObjectRequest):
    """
    Register or update an object in the linking registry.
    Consuming applications must call this on entity creation and on title updates.
    """
    _service.register_object(
        object_id=request.object_id,
        object_type=request.object_type,
        workspace_id=request.workspace_id,
        title=request.title,
    )


@router.get("/linking/objects/search", response_model=SearchObjectsResponse)
def search_objects(
    type: str,
    q: str,
    workspace_id: str | None = None,
    exclude_object_id: str | None = None,
    limit: int = 10,
):
    """
    Fuzzy title search within a given object type and workspace.
    Excludes exclude_object_id from results (used to hide the source object).
    """
    results = _service.search_objects(
        object_type=type,
        query=q,
        workspace_id=workspace_id,
        exclude_object_id=exclude_object_id,
        limit=limit,
    )
    return SearchObjectsResponse(objects=results)
