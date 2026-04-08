"""
LinkingEngine — links router.

Endpoints:
  POST   /linking/links
  DELETE /linking/links/{link_id}
  GET    /linking/links
  GET    /linking/objects/{object_id}/links

Source of truth: 20_design/architecture.json interfaces.exposed_surfaces
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models import (
    CreateLinkRequest,
    GetLinksResponse,
    LinkRecord,
)
from app.service import LinkService

router = APIRouter()
_service = LinkService()

# Error code → HTTP status mapping
_ERROR_STATUS: dict[str, int] = {
    "OBJECT_NOT_FOUND":            404,
    "SELF_LINK_NOT_ALLOWED":       422,
    "RELATION_INPUT_UNRECOGNIZED": 422,
    "INVALID_RELATION":            422,
    "INVALID_OBJECT_TYPE_PAIR":    422,
    "CYCLE_DETECTED":              422,
    "DUPLICATE_LINK":              409,
}


@router.post("/linking/links", response_model=LinkRecord)
def create_link(request: CreateLinkRequest):
    """
    Create a new link between two objects.
    Accepts free-text relation_input; normalization is performed server-side.
    """
    try:
        return _service.create_link(request)
    except ValueError as exc:
        code = str(exc)
        status = _ERROR_STATUS.get(code, 400)
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": code.replace("_", " ").capitalize()}},
        )


@router.delete("/linking/links/{link_id}")
def archive_link(link_id: str):
    """Soft-delete a link by setting archived_at."""
    found = _service.archive_link(link_id)
    if not found:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "LINK_NOT_FOUND", "message": "Link not found or already archived"}},
        )
    return {"archived": True}


@router.get("/linking/links", response_model=GetLinksResponse)
def get_links(
    from_object_id: str | None = None,
    to_object_id: str | None = None,
    relation_key: str | None = None,
):
    """Raw link query with optional filters. Returns active links only."""
    links = _service.get_links(
        from_object_id=from_object_id,
        to_object_id=to_object_id,
        relation_key=relation_key,
    )
    return GetLinksResponse(links=links)


@router.get("/linking/objects/{object_id}/links")
def get_links_for_object(object_id: str, workspace_id: str | None = None):
    """
    Return grouped, display-ready links for any object.
    Groups are ordered by relation sort_order; forward/reverse labels are resolved automatically.
    """
    groups = _service.get_links_for_object(
        object_id=object_id,
        workspace_id=workspace_id,
    )
    return {"object_id": object_id, "groups": [g.model_dump() for g in groups]}
