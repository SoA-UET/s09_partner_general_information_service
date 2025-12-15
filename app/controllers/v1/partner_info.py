"""
Partner Information Controller

HTTP API endpoints for Partner Portal to manage partner information.
Implements H25 and H26 API groups.
"""

from flask import request
from flask_restx import Namespace, Resource, fields
from ...utils.db import serialize_mongo_doc
from ...utils.auth import jwt_required

#######################################
## STEP 1. DECLARE THE API NAMESPACE ##
#######################################

api = Namespace('partner', description='Partner General Information Service (S09) APIs')

####################################
## STEP 2. DEFINE THE MODELS/DTOs ##
####################################

# H25: Partner Info DTOs
partner_info_dto = api.model("PartnerInfo", {
    "partner_id": fields.String(description="ID của partner, được Core gán"),
    "name": fields.String(description="Tên nhà mạng (VD: Vinaphone, Viettel)"),
    "api_key": fields.String(description="API key để xác thực với Core"),
    "core_url": fields.String(description="Endpoint API của hệ thống Core"),
    "created_at": fields.DateTime(description="Thời gian tạo"),
    "updated_at": fields.DateTime(description="Thời gian cập nhật gần nhất"),
})

partner_info_update_dto = api.model("PartnerInfoUpdate", {
    "partner_id": fields.String(required=False, description="ID của partner, được Core gán"),
    "name": fields.String(required=False, description="Tên nhà mạng"),
    "api_key": fields.String(required=False, description="API key để xác thực với Core"),
    "core_url": fields.String(required=False, description="Endpoint API của hệ thống Core"),
})

partner_info_response_dto = api.model("PartnerInfoResponse", {
    "status": fields.String(description="success hoặc error"),
    "data": fields.Nested(partner_info_dto, skip_none=True),
    "message": fields.String(description="Mô tả lỗi nếu status là error"),
})

# H26: Core Connection Test DTOs
core_connection_test_dto = api.model("CoreConnectionTest", {
    "core_url": fields.String(required=True, description="URL của Core API"),
    "api_key": fields.String(required=True, description="API key để xác thực"),
})

core_connection_test_result_dto = api.model("CoreConnectionTestResult", {
    "partner_id": fields.String(description="Partner ID được trả về từ Core"),
})

core_connection_test_response_dto = api.model("CoreConnectionTestResponse", {
    "status": fields.String(description="success hoặc error"),
    "message": fields.Raw(description="Kết quả test hoặc mô tả lỗi"),
})

##################################
## STEP 3. CONNECT THE SERVICES ##
##################################

from ...services import partner_information_service

###################################
## STEP 4. DEFINE THE CONTROLLER ##
###################################

@api.route("/info")
class PartnerInfoResource(Resource):
    """H25 API: Get and Update Partner Information"""
    
    service = partner_information_service
    
    @api.doc(description="Lấy thông tin partner hiện tại (H25)")
    @api.marshal_with(partner_info_response_dto)
    @jwt_required
    def get(self):
        """GET AUTH /api/partner/info - Get current partner general information"""
        try:
            partner_info = self.service.get_partner_info()
            
            if partner_info is None:
                return {
                    "status": "error",
                    "message": "Partner information not found"
                }, 404
            
            return {
                "status": "success",
                "data": serialize_mongo_doc(partner_info)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }, 500
    
    @api.doc(description="Cập nhật thông tin partner (H25)")
    @api.expect(partner_info_update_dto)
    @api.marshal_with(partner_info_response_dto)
    @jwt_required
    def patch(self):
        """PATCH AUTH /api/partner/info - Update partner general information"""
        try:
            data = request.get_json()
            
            if not data:
                return {
                    "status": "error",
                    "message": "Request body is required"
                }, 400
            
            # Filter allowed fields
            allowed_fields = ["partner_id", "name", "api_key", "core_url"]
            update_data = {k: v for k, v in data.items() if k in allowed_fields}
            
            if not update_data:
                return {
                    "status": "error",
                    "message": "No valid fields to update"
                }, 400
            
            updated_info = self.service.update_partner_info(update_data)
            
            return {
                "status": "success",
                "data": serialize_mongo_doc(updated_info)
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }, 500


@api.route("/core-connection/test")
class CoreConnectionTestResource(Resource):
    """H26 API: Test Core Connection"""
    
    service = partner_information_service
    
    @api.doc(description="Test kết nối tới Telcenter Core (H26)")
    @api.expect(core_connection_test_dto)
    @api.marshal_with(core_connection_test_response_dto)
    @jwt_required
    def post(self):
        """POST AUTH /api/partner/core-connection/test - Test connection to Core"""
        try:
            data = request.get_json()
            
            if not data:
                return {
                    "status": "error",
                    "message": "Request body is required"
                }, 400
            
            core_url = data.get("core_url")
            api_key = data.get("api_key")
            
            if not core_url or not api_key:
                return {
                    "status": "error",
                    "message": "core_url and api_key are required"
                }, 400
            
            # Test the connection using H11 API
            result = self.service.test_core_connection(core_url, api_key)
            
            return {
                "status": "success",
                "message": {
                    "partner_id": result.get("partner_id", "")
                }
            }
        except ConnectionError as e:
            return {
                "status": "error",
                "message": str(e)
            }, 400
        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }, 500
