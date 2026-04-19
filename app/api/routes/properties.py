from fastapi import APIRouter
from fastapi.responses import JSONResponse
router = APIRouter(prefix="/api/properties", tags=["properties"])
@router.get("/")
async def stub(): return JSONResponse(status_code=501, content={"detail": "Not implemented - Phase 2"})
