import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "Naqid (ناقد)"
    assert "has_gemini_key" in data
    print("Health check endpoint test passed!")

def test_demo_static_page():
    response = client.get("/demo/broken_page.html")
    assert response.status_code == 200
    assert "متجر الأفق" in response.text
    print("Demo static page serving test passed!")

def test_frontend_index():
    response = client.get("/")
    assert response.status_code == 200
    assert "ناقد - وكيل التدقيق الذكي" in response.text
    print("Frontend index serving test passed!")

def test_audit_invalid_url():
    response = client.post("/api/audit", json={"url": "not-a-valid-url", "demo": False})
    assert response.status_code == 400
    assert "صيغة الرابط غير صحيحة" in response.json()["detail"]
    print("Invalid URL error handling test passed!")

def test_audit_empty_url():
    response = client.post("/api/audit", json={"url": "", "demo": False})
    assert response.status_code == 400
    assert "يرجى إدخال رابط صالح للفحص" in response.json()["detail"]
    print("Empty URL error handling test passed!")

def test_audit_demo_mode():
    response = client.post("/api/audit", json={
        "url": "http://localhost:8000/demo/broken_page.html",
        "demo": True
    })
    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "score" in data
    assert "issues" in data
    assert len(data["issues"]) == 10
    assert "screenshots" in data
    assert "signals" in data
    assert "summary" in data
    assert "duration_seconds" in data
    print(f"Audit demo mode test passed! Issues: {len(data['issues'])}, Score: {data['score']}")

if __name__ == "__main__":
    test_health_endpoint()
    test_demo_static_page()
    test_frontend_index()
    test_audit_invalid_url()
    test_audit_empty_url()
    test_audit_demo_mode()
    print("ALL API TESTS PASSED!")
