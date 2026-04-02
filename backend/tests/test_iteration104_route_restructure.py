from conftest import TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD, BASE_URL
"""
Iteration 104 Tests — Route Directory Restructuring + AI Summarization + BM25 + Staleness + Pinned Shortcuts

Tests:
1. Backend health check after route restructuring (88 files moved to backend/routes/)
2. Auth login works correctly after restructuring  
3. GET workspaces returns data after restructuring
4. POST train/text creates chunks and triggers background enrichment
5. GET train/staleness returns staleness data with correct fields
6. POST knowledge/query returns relevant results
"""

import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    BASE_URL = "http://localhost:8080"

# Test credentials
TEST_EMAIL = TEST_ADMIN_EMAIL
TEST_PASSWORD = "test"
TEST_WORKSPACE_ID = "ws_a92cb83bfdb2"
TEST_AGENT_ID = "nxa_80888f5c29d3"


class TestRouteRestructuring:
    """Test backend after 88 route files moved to backend/routes/"""

    def test_health_check_healthy(self, api_client):
        """Backend health check returns healthy after route restructuring"""
        response = api_client.get(f"{BASE_URL}/api/health")
        assert response.status_code == 200, f"Health check failed: {response.text}"
        data = response.json()
        assert data["status"] == "healthy", f"Unhealthy status: {data}"
        assert data["database"] == "connected", f"DB not connected: {data}"
        assert "instance_id" in data, "Missing instance_id"
        print(f"PASS: Health check returned healthy with instance_id: {data['instance_id']}")

    def test_login_works(self, api_client):
        """POST /api/auth/login works correctly after route restructuring"""
        response = api_client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        # User data is returned directly in response (not nested under "user" key)
        assert "email" in data, "Missing email in response"
        assert "user_id" in data, "Missing user_id in response"
        assert data["email"] == TEST_EMAIL, f"Email mismatch: expected {TEST_EMAIL}, got {data['email']}"
        # Session token is set via cookie, not in JSON response
        assert "session_token" in response.cookies or any("session_token" in str(c) for c in response.cookies), "Missing session_token cookie"
        print(f"PASS: Login successful for {TEST_EMAIL}")

    def test_workspaces_list(self, authenticated_client):
        """GET /api/workspaces returns workspaces after restructuring"""
        response = authenticated_client.get(f"{BASE_URL}/api/workspaces")
        assert response.status_code == 200, f"Workspaces failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        # Should have at least the test workspace
        workspace_ids = [w["workspace_id"] for w in data]
        assert TEST_WORKSPACE_ID in workspace_ids, f"Test workspace {TEST_WORKSPACE_ID} not found in {workspace_ids}"
        print(f"PASS: Workspaces returned {len(data)} workspaces including test workspace")


class TestAgentTraining:
    """Test training endpoints with AI summarization + BM25 enrichment"""

    def test_train_text_creates_chunks(self, authenticated_client):
        """POST /api/workspaces/{ws}/agents/{agent}/train/text creates chunks and triggers background enrichment"""
        payload = {
            "title": "TEST_ITER104_Training",
            "content": "Machine learning is a subset of artificial intelligence that enables systems to learn from data. Neural networks are computational models inspired by biological neurons. Deep learning uses multiple layers to progressively extract higher-level features from raw input.",
            "topic": "ai_fundamentals"
        }
        response = authenticated_client.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/agents/{TEST_AGENT_ID}/train/text",
            json=payload
        )
        assert response.status_code == 200, f"Train text failed: {response.text}"
        data = response.json()
        assert "session_id" in data, "Missing session_id"
        assert "total_chunks" in data, "Missing total_chunks"
        assert data["total_chunks"] > 0, f"No chunks created: {data}"
        print(f"PASS: Created {data['total_chunks']} chunks, session={data['session_id']}")
        # Background enrichment (AI summarization + BM25) runs async, not directly testable
        return data

    def test_staleness_endpoint_returns_data(self, authenticated_client):
        """GET /api/workspaces/{ws}/agents/{agent}/train/staleness returns staleness data"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/agents/{TEST_AGENT_ID}/train/staleness?threshold_days=30"
        )
        assert response.status_code == 200, f"Staleness failed: {response.text}"
        data = response.json()
        
        # Required fields per spec
        assert "total_chunks" in data, "Missing total_chunks"
        assert "stale_count" in data, "Missing stale_count"
        assert "fresh_count" in data, "Missing fresh_count"
        assert "never_used_count" in data, "Missing never_used_count"
        assert "topic_staleness" in data, "Missing topic_staleness"
        assert "threshold_days" in data, "Missing threshold_days"
        assert "staleness_pct" in data, "Missing staleness_pct"
        
        # Type checks
        assert isinstance(data["total_chunks"], int), "total_chunks should be int"
        assert isinstance(data["stale_count"], int), "stale_count should be int"
        assert isinstance(data["fresh_count"], int), "fresh_count should be int"
        assert isinstance(data["never_used_count"], int), "never_used_count should be int"
        assert isinstance(data["topic_staleness"], dict), "topic_staleness should be dict"
        
        print(f"PASS: Staleness data returned - total={data['total_chunks']}, stale={data['stale_count']}, fresh={data['fresh_count']}, never_used={data['never_used_count']}")
        return data

    def test_knowledge_query_returns_results(self, authenticated_client):
        """POST /api/workspaces/{ws}/agents/{agent}/knowledge/query returns relevant results"""
        payload = {"query": "machine learning neural networks", "top_k": 5}
        response = authenticated_client.post(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/agents/{TEST_AGENT_ID}/knowledge/query",
            json=payload
        )
        assert response.status_code == 200, f"Query failed: {response.text}"
        data = response.json()
        
        assert "results" in data, "Missing results"
        assert "total_searched" in data, "Missing total_searched"
        assert isinstance(data["results"], list), "results should be list"
        
        # If there are results, check structure
        if data["results"]:
            result = data["results"][0]
            assert "chunk_id" in result, "Missing chunk_id in result"
            assert "content" in result or "text" in result, "Missing content in result"
            assert "relevance_score" in result, "Missing relevance_score in result"
        
        print(f"PASS: Knowledge query returned {len(data['results'])} results from {data['total_searched']} chunks searched")

    def test_knowledge_stats(self, authenticated_client):
        """GET /api/workspaces/{ws}/agents/{agent}/knowledge/stats returns stats"""
        response = authenticated_client.get(
            f"{BASE_URL}/api/workspaces/{TEST_WORKSPACE_ID}/agents/{TEST_AGENT_ID}/knowledge/stats"
        )
        assert response.status_code == 200, f"Stats failed: {response.text}"
        data = response.json()
        
        assert "total_chunks" in data, "Missing total_chunks"
        assert "flagged" in data, "Missing flagged"
        assert "active" in data, "Missing active"
        
        print(f"PASS: Knowledge stats - total={data['total_chunks']}, flagged={data['flagged']}, active={data['active']}")


class TestAISummarization:
    """Test AI summarization module (Claude Sonnet 4.5 via direct API)"""

    def test_ai_summarizer_import(self):
        """AI summarizer module imports correctly"""
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from ai_summarizer import summarize_chunk, summarize_chunks_batch
            print("PASS: ai_summarizer module imports correctly")
        except ImportError as e:
            pytest.fail(f"Failed to import ai_summarizer: {e}")


class TestBM25Embeddings:
    """Test BM25 embedding module"""

    def test_bm25_embeddings_import(self):
        """BM25 embeddings module imports correctly"""
        try:
            import sys
            sys.path.insert(0, "/app/backend")
            from ai_embeddings import (
                tokenize, ngrams, extract_features, 
                compute_bm25_vectors, compute_query_vector, cosine_similarity
            )
            print("PASS: ai_embeddings module imports correctly")
        except ImportError as e:
            pytest.fail(f"Failed to import ai_embeddings: {e}")

    def test_bm25_tokenize(self):
        """BM25 tokenizer works correctly"""
        import sys
        sys.path.insert(0, "/app/backend")
        from ai_embeddings import tokenize, extract_features
        
        tokens = tokenize("Machine Learning is amazing!")
        assert "machine" in tokens, "Missing 'machine'"
        assert "learning" in tokens, "Missing 'learning'"
        assert "is" in tokens, "Missing 'is'"
        
        features = extract_features("neural networks deep learning")
        # Should have unigrams + bigrams
        assert "neural" in features, "Missing unigram 'neural'"
        assert "networks" in features, "Missing unigram 'networks'"
        assert "neural_networks" in features, "Missing bigram 'neural_networks'"
        
        print("PASS: BM25 tokenizer and feature extraction work correctly")

    def test_bm25_vector_computation(self):
        """BM25 vector computation works"""
        import sys
        sys.path.insert(0, "/app/backend")
        from ai_embeddings import compute_bm25_vectors, cosine_similarity
        
        docs = [
            "machine learning algorithms",
            "neural networks deep learning",
            "data science statistics"
        ]
        vocab, idf, vectors = compute_bm25_vectors(docs)
        
        assert len(vocab) > 0, "Empty vocabulary"
        assert len(idf) > 0, "Empty IDF scores"
        assert len(vectors) == len(docs), "Vector count mismatch"
        
        print(f"PASS: BM25 vectors computed - vocab_size={len(vocab)}, docs={len(docs)}")


class TestRoutesDirectoryStructure:
    """Verify routes directory structure after restructuring"""

    def test_routes_directory_exists(self):
        """Backend routes directory exists with expected files"""
        import os
        routes_dir = "/app/backend/routes"
        assert os.path.exists(routes_dir), f"Routes directory missing: {routes_dir}"
        
        files = os.listdir(routes_dir)
        assert "__init__.py" in files, "Missing __init__.py"
        assert "routes_agent_training.py" in files, "Missing routes_agent_training.py"
        assert "routes_auth_email.py" in files, "Missing routes_auth_email.py"
        assert "routes_workspaces.py" in files, "Missing routes_workspaces.py"
        
        route_files = [f for f in files if f.startswith("routes_") and f.endswith(".py")]
        assert len(route_files) >= 80, f"Expected 80+ route files, found {len(route_files)}"
        
        print(f"PASS: Routes directory has {len(route_files)} route files + __init__.py")


# Fixtures
@pytest.fixture
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture
def authenticated_client(api_client):
    """Session with auth token from cookies"""
    response = api_client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    
    # Session token is set via cookie automatically by requests.Session
    # The cookie should be available for subsequent requests
    token = response.cookies.get("session_token")
    if token:
        api_client.headers.update({"Authorization": f"Bearer {token}"})
    
    return api_client
