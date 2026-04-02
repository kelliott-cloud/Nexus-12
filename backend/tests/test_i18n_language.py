"""
Tests for i18n/localization language preference endpoints
- PUT /api/user/language endpoint saves language preference
- Backend accepts 'en' and 'es', rejects invalid languages
"""
import pytest
import requests
import os

# Get BASE_URL from env var or .env file
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    try:
        _env_path = str(__import__('pathlib').Path(__file__).resolve().parent.parent.parent / 'frontend' / '.env')
        with open(_env_path, 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    BASE_URL = line.strip().split('=', 1)[1].rstrip('/')
                    break
    except Exception:
        BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

if not BASE_URL:
    raise RuntimeError("BASE_URL not found in /app/frontend/.env")

# Session tokens from test credentials
SUPER_ADMIN_TOKEN = "Fp_kWAvgxh8krRP-eEhEicsB06MwP3UtRkzlM66fMVA"


@pytest.fixture
def auth_session():
    """Create authenticated session using super admin token"""
    session = requests.Session()
    session.cookies.set('session_token', SUPER_ADMIN_TOKEN)
    session.headers.update({'Content-Type': 'application/json'})
    return session


class TestLanguagePreferenceAPI:
    """Tests for PUT /api/user/language endpoint"""
    
    def test_update_language_to_es(self, auth_session):
        """Test changing language to Spanish"""
        response = auth_session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "es"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "updated"
        assert data.get("language") == "es"
        print("✓ Language updated to 'es' successfully")
    
    def test_update_language_to_en(self, auth_session):
        """Test changing language back to English"""
        response = auth_session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "en"}
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("status") == "updated"
        assert data.get("language") == "en"
        print("✓ Language updated to 'en' successfully")
    
    def test_reject_invalid_language(self, auth_session):
        """Test that invalid languages are rejected"""
        invalid_languages = ["fr", "de", "zh", "invalid", "ENGLISH", "ES", ""]
        
        for lang in invalid_languages:
            response = auth_session.put(
                f"{BASE_URL}/api/user/language",
                json={"language": lang}
            )
            
            assert response.status_code == 400, f"Expected 400 for '{lang}', got {response.status_code}"
            print(f"✓ Invalid language '{lang}' correctly rejected with 400")
    
    def test_language_persists_in_user_data(self, auth_session):
        """Test that language preference persists to user document"""
        # First set to Spanish
        response = auth_session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "es"}
        )
        assert response.status_code == 200
        
        # Fetch user data and verify language is set
        me_response = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        
        user_data = me_response.json()
        assert user_data.get("language") == "es", f"Expected language 'es', got: {user_data.get('language')}"
        print("✓ Language 'es' persisted in user document")
        
        # Reset to English
        response = auth_session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "en"}
        )
        assert response.status_code == 200
        
        me_response = auth_session.get(f"{BASE_URL}/api/auth/me")
        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data.get("language") == "en", f"Expected language 'en', got: {user_data.get('language')}"
        print("✓ Language 'en' persisted in user document")


class TestLanguageEndpointAuth:
    """Test authentication requirements for language endpoint"""
    
    def test_unauthenticated_rejected(self):
        """Test that unauthenticated requests are rejected"""
        session = requests.Session()
        session.headers.update({'Content-Type': 'application/json'})
        
        response = session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "es"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Unauthenticated request correctly rejected with 401")
    
    def test_invalid_session_rejected(self):
        """Test that invalid session token is rejected"""
        session = requests.Session()
        session.cookies.set('session_token', 'invalid-token-12345')
        session.headers.update({'Content-Type': 'application/json'})
        
        response = session.put(
            f"{BASE_URL}/api/user/language",
            json={"language": "es"}
        )
        
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid session token correctly rejected with 401")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
