from fastapi import APIRouter
from starlette import status
from starlette.responses import Response

from app.api.dependencies import DbTransaction
from app.models import PostHogEvent
from app.services.event_services import insert_raw_event

router = APIRouter()


@router.post("/ingest")
async def ingest(input_data: PostHogEvent, db: DbTransaction) -> Response:
    await insert_raw_event(connection=db, event=input_data)
    return Response(status_code=status.HTTP_202_ACCEPTED)
