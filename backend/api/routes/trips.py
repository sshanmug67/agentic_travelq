"""
Fixed Trip Search Route
Location: backend/api/routes/trips.py
"""
from fastapi import APIRouter, HTTPException
from models.trip import TripRequest, TripResponse
from services.trip_planning_service import trip_planning_service
from utils.logging_config import log_info_raw, log_json_raw, log_error_raw

router = APIRouter(prefix="/api/trips", tags=["trips"])

@router.post("/search", response_model=TripResponse)
async def search_trip(request: TripRequest):
    """
    Search and plan a trip based on user preferences
    """
    log_info_raw("=" * 80)
    log_info_raw("🌐 HTTP POST /api/trips/search - Request received")
    log_info_raw("=" * 80)
    
    try:
        # Log incoming request
        log_json_raw({
            "endpoint": "/api/trips/search",
            "method": "POST",
            "origin": request.origin,
            "destination": request.destination,
            "departure_date": request.departure_date,
            "return_date": request.return_date,
            "num_travelers": request.num_travelers
        }, label="📨 Incoming Request Summary")
        
        log_info_raw("📤 Delegating to TripPlanningService...")
        
        # Call service
        result = await trip_planning_service.plan_trip(request)
        
        # ✅ FIX: Don't pass status twice - result already has it
        response = TripResponse(**result)  # Just unpack the dict
        
        log_info_raw("=" * 80)
        log_info_raw("✅ HTTP 200 - Success")
        log_info_raw("=" * 80)
        
        return response
        
    except ValueError as e:
        # Validation errors (400)
        log_error_raw("=" * 80)
        log_error_raw(f"❌ HTTP 400 - Bad Request")
        log_error_raw(f"Error: {str(e)}")
        log_error_raw("=" * 80)
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        # Server errors (500)
        log_error_raw("=" * 80)
        log_error_raw(f"❌ HTTP 500 - Internal Server Error")
        log_error_raw(f"Error: {str(e)}")
        log_error_raw("=" * 80)
        
        import traceback
        log_error_raw("Full traceback:")
        log_error_raw(traceback.format_exc())
        
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "TravelQ API",
        "version": "1.0.0"
    }