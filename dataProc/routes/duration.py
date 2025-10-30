from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict, Optional
import os

from services.duration_service import run_duration_job


router = APIRouter(prefix="/v1", tags=["duration"])


@router.post("/duration")
def duration_endpoint(body: Optional[Dict[str, Any]] = Body(None)):
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        # K is hardcoded; ignore body parameters
        result = run_duration_job(data_dir=data_dir)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Duration job failed: {str(e)}")
