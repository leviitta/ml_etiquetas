import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.db.quota import ensure_user, get_quota_status
from starlette.config import Config
from authlib.integrations.starlette_client import OAuth

router = APIRouter()
config = Config('.env')
oauth = OAuth(config)

oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Variable estática cargada desde el entorno para mayor seguridad OAuth
STATIC_BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")

@router.get('/login')
async def login(request: Request, intent_plan: str = None):
    if intent_plan:
        request.session['intent_plan'] = intent_plan
    
    redirect_uri = f"{STATIC_BASE_URL}/api/v1/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/callback', name='auth_callback')
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # User might have denied access or mismatching state
        return RedirectResponse(url='/api/v1/')
    
    # Obtenemos la info del usuario
    user = token.get('userinfo')
    email = None
    if user:
        request.session['user'] = dict(user)
        email = user.get("email")
        name = user.get("name", "")
        if email:
            await ensure_user(email, name)
            
    intent_plan = request.session.pop('intent_plan', None)
    if intent_plan and email:
        quota_status = await get_quota_status(email)
        current_plan = quota_status.get("active_plan_type", "starter")
        
        if current_plan == "infinity":
            return RedirectResponse(url='/api/v1/?payment=already_infinity')
            
        elif current_plan == "pro":
            if intent_plan == "infinity":
                return RedirectResponse(url=f'/api/v1/?checkout_plan={intent_plan}')
            else:
                return RedirectResponse(url='/api/v1/?payment=already_pro')
                
        else:
            return RedirectResponse(url=f'/api/v1/?checkout_plan={intent_plan}')
        
    return RedirectResponse(url='/api/v1/')

@router.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/api/v1/')
