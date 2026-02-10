"""
Updated Trip Planning Service
Location: backend/services/trip_planning_service.py
"""
from typing import Dict, Any
from datetime import datetime

from models.trip import TripRequest
from agents.user_proxy_agent import TravelQUserProxy
from agents.orchestrator_agent import TravelOrchestratorAgent
from utils.request_converter import convert_trip_request_to_preferences, validate_trip_request
from utils.logging_config import log_info_raw, log_json_raw, log_error_raw

class TripPlanningService:
    
    async def plan_trip(self, trip_request: TripRequest) -> Dict[str, Any]:
        """
        Plan trip - orchestrator handles storage now
        """
        start_time = datetime.now()
        
        log_info_raw("=" * 80)
        log_info_raw("📋 TripPlanningService: Starting trip planning")
        log_info_raw("=" * 80)
        
        try:
            # Validate and convert
            request_dict = trip_request.model_dump()
            is_valid, error_msg = validate_trip_request(request_dict)
            if not is_valid:
                raise ValueError(error_msg)
            
            travel_preferences = convert_trip_request_to_preferences(request_dict)
            
            # Create user proxy
            user_proxy = TravelQUserProxy(
                name="APIUser",
                user_preferences=travel_preferences,
                human_input_mode="NEVER"
            )
            
            # Create orchestrator
            orchestrator = TravelOrchestratorAgent()
            
            # Orchestrate (handles storage internally)
            result = await orchestrator.orchestrate(user_proxy)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # ✅ No extraction needed - orchestrator returns everything!
            log_info_raw("=" * 80)
            log_info_raw("✅ Trip planning completed successfully")
            log_json_raw({
                "trip_id": result["trip_id"],
                "flights_reviewed": len(result["all_options"]["flights"]),
                "hotels_reviewed": len(result["all_options"]["hotels"]),
                "processing_time": f"{processing_time:.2f}s"
            }, label="Results Summary")
            log_info_raw("=" * 80)
            
            return {
                "status": "success",
                "trip_id": result["trip_id"],
                "final_recommendation": result["final_recommendation"],
                "options": result["all_options"],
                "summary": result["summary"],
                "processing_time": processing_time,
                "agents_used": result["agents_used"]
            }
            
        except Exception as e:
            log_error_raw(f"❌ Trip planning failed: {str(e)}")
            raise Exception(f"Trip planning failed: {str(e)}")


trip_planning_service = TripPlanningService()