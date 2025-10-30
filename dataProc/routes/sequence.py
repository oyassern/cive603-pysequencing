from fastapi import APIRouter, HTTPException
from typing import Any, Dict, Optional
import os
import json

from services.sequence_service import run_sequence_job


router = APIRouter(prefix="/v1", tags=["sequence"])


@router.post("/sequence")
def sequence_endpoint():
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        result = run_sequence_job(data_dir=data_dir)
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sequence job failed: {str(e)}")
