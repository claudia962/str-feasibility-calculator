from fastapi import APIRouter
from fastapi.responses import JSONResponse
router = APIRouter(prefix="/api/comps", tags=["comps"])
@router.get("/{feasibility_id}")
async def stub(feasibility_id: str): return JSONResponse(status_code=501, content={"detail": "Not implemented - Phase 2"})
