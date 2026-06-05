import csv
import io
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth_utils import require_admin
from app.database import get_db
from app.models import MessageLog, SimulationSession, User

router = APIRouter(prefix="/export", tags=["export"])


@router.get("/logs")
async def export_logs(
    format: str = Query("json", pattern="^(json|csv)$"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(MessageLog)
        .join(SimulationSession)
        .options(selectinload(MessageLog.session).selectinload(SimulationSession.user))
        .order_by(MessageLog.timestamp)
    )
    messages = result.scalars().all()

    rows = []
    for msg in messages:
        user_email = msg.session.user.email if msg.session.user else None
        rows.append(
            {
                "session_id": str(msg.session_id),
                "timestamp": msg.timestamp.isoformat(),
                "sender_role": msg.sender_role.value,
                "content": msg.content,
                "user_email": user_email,
            }
        )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        content = json.dumps(rows, indent=2, ensure_ascii=False)
        return StreamingResponse(
            iter([content]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="transcript_logs_{timestamp}.json"'},
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["session_id", "timestamp", "sender_role", "content", "user_email"],
    )
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="transcript_logs_{timestamp}.csv"'},
    )
