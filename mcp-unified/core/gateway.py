import httpx
import logging
from fastapi import APIRouter
from starlette.responses import StreamingResponse, JSONResponse
from starlette.exceptions import HTTPException

# Configure basic logging for the gateway
logger = logging.getLogger("gateway")

router = APIRouter(prefix="/gateway", tags=["gateway"])

# Map of internal services to their local ports/URLs
SERVICE_MAP = {
    "korespondensi": "http://localhost:8082",
    "vane": "http://localhost:3002",
    "waha": "http://localhost:3000",
}

async def reverse_proxy_gateway(request):
    """
    Universal Reverse Proxy Gateway using Starlette directly.
    """
    # Extract path parameters from Starlette scope
    service_name = request.path_params.get("service_name")
    path = request.path_params.get("path", "")

    if service_name not in SERVICE_MAP:
        return JSONResponse({"error": f"Service '{service_name}' not found"}, status_code=404)

    target_base_url = SERVICE_MAP[service_name]
    clean_path = path if path.startswith("/") else f"/{path}"
    target_url = f"{target_base_url}{clean_path}"
    
    if request.query_params:
        target_url = f"{target_url}?{request.query_params}"

    # Prepare proxy request
    client = httpx.AsyncClient(base_url=target_base_url, timeout=60.0)
    
    try:
        headers = dict(request.headers)
        headers.pop("host", None)
        body = await request.body()

        rp_req = client.build_request(
            request.method,
            target_url,
            headers=headers,
            content=body
        )

        rp_resp = await client.send(rp_req, stream=True)
        
        return StreamingResponse(
            rp_resp.aiter_raw(),
            status_code=rp_resp.status_code,
            headers=dict(rp_resp.headers)
        )
    except httpx.ConnectError:
        return JSONResponse({"error": f"Service '{service_name}' unreachable at {target_base_url}"}, status_code=502)
    except Exception as e:
        logger.error(f"Gateway error: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)
    finally:
        # Note: In a real app, we should reuse the client
        # but for simplicity we close it here.
        await client.aclose()


@router.api_route("/{service_name}/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def gateway_proxy(request):
    return await reverse_proxy_gateway(request)


@router.api_route("/{service_name}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def gateway_proxy_root(request):
    return await reverse_proxy_gateway(request)
