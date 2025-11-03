from fastapi import APIRouter, HTTPException, Body
from typing import Any, Dict
import os

from services.critical_service import run_critical_job


router = APIRouter(prefix="/v1", tags=["critical"])


@router.post("/critical")
def critical_endpoint(body: Any = Body(...)):
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        result = run_critical_job(data_dir=data_dir, extra_body=body)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Critical path job failed: {str(e)}")

