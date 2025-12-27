"""Tests for the FamiLator web interface."""

import json
import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from web.app import create_app


@pytest.fixture
def app():
    """Create test application."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "UPLOAD_FOLDER": os.path.join(tmpdir, "roms"),
            "OUTPUT_FOLDER": os.path.join(tmpdir, "output"),
        }
        # Create the directories since we're using absolute paths in tests
        os.makedirs(config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(config["OUTPUT_FOLDER"], exist_ok=True)
        app = create_app(config)
        yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


class TestAppFactory:
    """Tests for application factory."""
    
    def test_create_app_returns_flask_instance(self, app):
        """Test that create_app returns a Flask instance."""
        from flask import Flask
        assert isinstance(app, Flask)
    
    def test_create_app_with_custom_config(self, app):
        """Test that custom config is applied."""
        assert app.config["TESTING"] is True
        assert app.config["SECRET_KEY"] == "test-secret-key"
    
    def test_folders_created(self, app):
        """Test that upload and output folders are created."""
        assert Path(app.config["UPLOAD_FOLDER"]).exists()
        assert Path(app.config["OUTPUT_FOLDER"]).exists()


class TestMainRoutes:
    """Tests for main page routes."""
    
    def test_index_page(self, client):
        """Test home page loads."""
        response = client.get("/")
        assert response.status_code == 200
        assert b"FamiLator" in response.data
    
    def test_upload_page_get(self, client):
        """Test upload page loads."""
        response = client.get("/upload")
        assert response.status_code == 200
        assert b"Upload ROM" in response.data
    
    def test_upload_no_file(self, client):
        """Test upload with no file selected."""
        response = client.post("/upload", follow_redirects=True)
        assert response.status_code == 200
        assert b"No file selected" in response.data
    
    def test_analyze_nonexistent_rom(self, client):
        """Test analyze page with nonexistent ROM."""
        response = client.get("/analyze/nonexistent.nes", follow_redirects=True)
        assert response.status_code == 200
        assert b"not found" in response.data


class TestAPIRoutes:
    """Tests for API endpoints."""
    
    def test_api_extract_no_filename(self, client):
        """Test extract API with missing filename."""
        response = client.post(
            "/api/extract",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    def test_api_extract_missing_rom(self, client):
        """Test extract API with nonexistent ROM."""
        response = client.post(
            "/api/extract",
            data=json.dumps({"rom_filename": "missing.nes"}),
            content_type="application/json"
        )
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "not found" in data["error"]
    
    def test_api_translate_no_project(self, client):
        """Test translate API with missing project."""
        response = client.post(
            "/api/translate",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    def test_api_check_font_empty(self, client):
        """Test font check API with empty text."""
        response = client.post(
            "/api/check_font",
            data=json.dumps({"text": ""}),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["compatible"] is True
    
    def test_api_check_font_ascii(self, client):
        """Test font check API with ASCII text."""
        response = client.post(
            "/api/check_font",
            data=json.dumps({"text": "Hello World"}),
            content_type="application/json"
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "compatible" in data
    
    def test_api_build_patch_no_project(self, client):
        """Test build patch API with missing project."""
        response = client.post(
            "/api/build_patch",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
    
    def test_api_validate_no_project(self, client):
        """Test validate API with missing project."""
        response = client.post(
            "/api/validate",
            data=json.dumps({}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data


class TestProjectRoutes:
    """Tests for project management routes."""
    
    def test_list_projects_empty(self, client):
        """Test project list with no projects."""
        response = client.get("/projects/")
        assert response.status_code == 200
        assert b"No Projects Yet" in response.data
    
    def test_new_project_page(self, client):
        """Test new project page loads."""
        response = client.get("/projects/new")
        assert response.status_code == 200
        assert b"Create New Project" in response.data
    
    def test_delete_nonexistent_project(self, client):
        """Test deleting nonexistent project."""
        response = client.post("/projects/nonexistent/delete", follow_redirects=True)
        assert response.status_code == 200
        assert b"not found" in response.data


class TestFileHelpers:
    """Tests for file helper functions."""
    
    def test_allowed_file_nes(self, app):
        """Test .nes files are allowed."""
        with app.app_context():
            from web.routes import allowed_file
            assert allowed_file("game.nes") is True
    
    def test_allowed_file_fds(self, app):
        """Test .fds files are allowed."""
        with app.app_context():
            from web.routes import allowed_file
            assert allowed_file("game.fds") is True
    
    def test_allowed_file_invalid(self, app):
        """Test invalid extensions are rejected."""
        with app.app_context():
            from web.routes import allowed_file
            assert allowed_file("game.exe") is False
            assert allowed_file("game.txt") is False
    
    def test_allowed_file_no_extension(self, app):
        """Test files without extensions are rejected."""
        with app.app_context():
            from web.routes import allowed_file
            assert allowed_file("gamefile") is False


class TestSaveTranslation:
    """Tests for save translation API."""
    
    def test_save_translation_missing_fields(self, client):
        """Test save translation with missing fields."""
        response = client.post(
            "/api/save_translation",
            data=json.dumps({"project_name": "test"}),
            content_type="application/json"
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "Missing required fields" in data["error"]
    
    def test_save_translation_missing_file(self, client):
        """Test save translation with missing translation file."""
        response = client.post(
            "/api/save_translation",
            data=json.dumps({
                "project_name": "nonexistent",
                "offset": "0x1000",
                "translated_text": "Test"
            }),
            content_type="application/json"
        )
        assert response.status_code == 404


class TestCHRTilesAPI:
    """Tests for CHR tiles API."""
    
    def test_chr_tiles_missing_rom(self, client):
        """Test CHR tiles API with missing ROM."""
        response = client.get("/api/chr_tiles/missing.nes")
        assert response.status_code == 404
        data = json.loads(response.data)
        assert "not found" in data["error"]
