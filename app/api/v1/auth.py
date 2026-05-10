import os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from dotenv import load_dotenv
from app.db.quota import ensure_user

load_dotenv()

router = APIRouter()

oauth = OAuth()
oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

@router.get('/login')
async def login(request: Request, intent_plan: str = None):
    if intent_plan:
        request.session['intent_plan'] = intent_plan
    client_base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{client_base_url}/api/v1/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/callback', name='auth_callback')
async def auth_callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception as e:
        # User might have denied access
        return RedirectResponse(url='/api/v1/')
    
    # Obtenemos la info del usuario
    user = token.get('userinfo')
    if user:
        request.session['user'] = dict(user)
        email = user.get("email")
        name = user.get("name", "")
        if email:
            await ensure_user(email, name)
            
    intent_plan = request.session.pop('intent_plan', None)
    if intent_plan:
        return RedirectResponse(url=f'/api/v1/?checkout_plan={intent_plan}')
        
    return RedirectResponse(url='/api/v1/')

@router.get('/logout')
async def logout(request: Request):
    request.session.pop('user', None)
    return RedirectResponse(url='/api/v1/')
