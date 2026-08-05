from fastapi import APIRouter

from app.schemas.graph import CommunityListResponse, CommunityResponse
from app.services import graph_store
from app.tasks.celery_app import celery_app
from app.tasks.community_detection import detect_communities_task

router = APIRouter(prefix="/graph/communities", tags=["communities"])


@router.post("/detect", status_code=202)
def detect_communities():
    """Kicks off a full corpus-wide rebuild in the background and returns
    immediately with a Celery task id — there's no `document_id` to poll via
    the usual `GET /documents/{id}` pattern, since this isn't scoped to one
    document. Poll `GET /graph/communities/status/{task_id}` instead.
    """
    task = detect_communities_task.delay()
    return {"task_id": task.id}


@router.get("/status/{task_id}")
def get_detection_status(task_id: str):
    result = celery_app.AsyncResult(task_id)
    response = {"task_id": task_id, "state": result.state}
    if result.state == "SUCCESS":
        response["result"] = result.result
    elif result.state == "FAILURE":
        response["error"] = str(result.result)
    return response


@router.get("", response_model=CommunityListResponse)
def list_communities():
    driver = graph_store.get_neo4j_driver()
    try:
        rows = graph_store.fetch_communities(driver)
    finally:
        driver.close()
    return CommunityListResponse(communities=[CommunityResponse(**row) for row in rows])
