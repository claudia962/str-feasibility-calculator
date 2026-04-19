from fastapi import APIRouter
from fastapi.responses import JSONResponse
router = APIRouter(prefix="/api/reports", tags=["reports"])
@router.get("/{feasibility_id}")
async def stub(feasibility_id: str): return JSONResponse(status_code=501, content={"detail": "Not implemented - Phase 5"})
