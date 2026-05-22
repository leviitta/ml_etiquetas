import pytest
from unittest.mock import AsyncMock, patch

class MockSession(dict):
    pass

@pytest.mark.asyncio
@patch('app.api.v1.auth.oauth.google.authorize_access_token')
@patch('app.api.v1.auth.ensure_user')
@patch('app.api.v1.auth.get_quota_status')
async def test_auth_callback_routing(mock_get_quota, mock_ensure_user, mock_authorize):
    """
    Test the intent_plan redirection logic after login.
    """
    # 1. Base mock setup
    mock_authorize.return_value = {
        'userinfo': {'email': 'test@example.com', 'name': 'Test User'}
    }
    mock_ensure_user.return_value = None
    
    # 2. Test scenario: User is free/starter and wants Pro
    mock_get_quota.return_value = {"active_plan_type": "starter"}
    
    from app.api.v1.auth import auth_callback
    from fastapi import Request
    
    mock_session = MockSession({'intent_plan': 'pro'})
    mock_request = AsyncMock(spec=Request)
    mock_request.session = mock_session
    
    response = await auth_callback(mock_request)
    assert response.status_code == 307
    assert response.headers['location'] == '/api/v1/?checkout_plan=pro'
        
    # 3. Test scenario: User is Pro and wants Infinity (Upgrade allowed)
    mock_get_quota.return_value = {"active_plan_type": "pro"}
    mock_session = MockSession({'intent_plan': 'infinity'})
    mock_request = AsyncMock(spec=Request)
    mock_request.session = mock_session
    
    response = await auth_callback(mock_request)
    assert response.status_code == 307
    assert response.headers['location'] == '/api/v1/?checkout_plan=infinity'
        
    # 4. Test scenario: User is Pro and clicks Pro again (Stop duplicate purchase)
    mock_get_quota.return_value = {"active_plan_type": "pro"}
    mock_session = MockSession({'intent_plan': 'pro'})
    mock_request = AsyncMock(spec=Request)
    mock_request.session = mock_session
    
    response = await auth_callback(mock_request)
    assert response.status_code == 307
    assert response.headers['location'] == '/api/v1/?payment=already_pro'
        
    # 5. Test scenario: User is Infinity and wants Pro (Already maxed)
    mock_get_quota.return_value = {"active_plan_type": "infinity"}
    mock_session = MockSession({'intent_plan': 'pro'})
    mock_request = AsyncMock(spec=Request)
    mock_request.session = mock_session
    
    response = await auth_callback(mock_request)
    assert response.status_code == 307
    assert response.headers['location'] == '/api/v1/?payment=already_infinity'

