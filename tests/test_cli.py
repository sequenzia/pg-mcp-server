"""Tests for CLI argument parsing and env file handling."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from pg_mcp_server.__main__ import parse_args, validate_env_file
from pg_mcp_server.config import get_env_file_path, set_env_file_path


class TestParseArgs:
    """Tests for CLI argument parsing."""

    def test_parse_args_no_arguments(self) -> None:
        """Test parsing with no arguments returns defaults."""
        with patch.object(sys, "argv", ["pg-mcp-server"]):
            args = parse_args()
            assert args.env_file is None

    def test_parse_args_with_env_file(self) -> None:
        """Test parsing with --env-file argument."""
        with patch.object(sys, "argv", ["pg-mcp-server", "--env-file", "/path/to/file.env"]):
            args = parse_args()
            assert args.env_file == "/path/to/file.env"

    def test_parse_args_with_env_file_equals_syntax(self) -> None:
        """Test parsing with --env-file=value syntax."""
        with patch.object(sys, "argv", ["pg-mcp-server", "--env-file=/path/to/file.env"]):
            args = parse_args()
            assert args.env_file == "/path/to/file.env"


class TestValidateEnvFile:
    """Tests for env file validation."""

    def test_validate_env_file_none(self) -> None:
        """Test validation with None returns None."""
        result = validate_env_file(None)
        assert result is None

    def test_validate_env_file_valid_file(self, tmp_path: Path) -> None:
        """Test validation with valid file returns resolved path."""
        env_file = tmp_path / "test.env"
        env_file.write_text("PG_HOST=localhost")

        result = validate_env_file(str(env_file))
        assert result == str(env_file.resolve())

    def test_validate_env_file_missing_file(self, tmp_path: Path) -> None:
        """Test validation with missing file exits with error."""
        missing_file = tmp_path / "missing.env"

        with pytest.raises(SystemExit) as exc_info:
            validate_env_file(str(missing_file))

        assert exc_info.value.code == 1

    def test_validate_env_file_directory(self, tmp_path: Path) -> None:
        """Test validation with directory path exits with error."""
        with pytest.raises(SystemExit) as exc_info:
            validate_env_file(str(tmp_path))

        assert exc_info.value.code == 1


class TestEnvFilePathState:
    """Tests for module-level env file path state management."""

    def test_get_env_file_path_default(self) -> None:
        """Test default env file path is None."""
        set_env_file_path(None)  # Reset first
        assert get_env_file_path() is None

    def test_set_and_get_env_file_path(self) -> None:
        """Test setting and getting env file path."""
        test_path = "/custom/path/to/.env"
        set_env_file_path(test_path)
        assert get_env_file_path() == test_path

    def test_set_env_file_path_to_none(self) -> None:
        """Test setting env file path back to None."""
        set_env_file_path("/some/path")
        set_env_file_path(None)
        assert get_env_file_path() is None


class TestSettingsWithEnvFile:
    """Integration tests for settings loading with custom env file."""

    def test_settings_loads_from_custom_env_file(self, tmp_path: Path) -> None:
        """Test that settings loads values from custom env file."""
        # Create a custom env file with test values
        env_file = tmp_path / "custom.env"
        env_file.write_text(
            "PG_HOST=custom-host\n"
            "PG_PORT=5433\n"
            "PG_DATABASE=custom_db\n"
            "PG_USER=custom_user\n"
            "PG_PASSWORD=custom_pass\n"
            "MCP_LOG_LEVEL=DEBUG\n"
        )

        # Set the custom env file path
        set_env_file_path(str(env_file))

        # Import get_settings here to avoid caching issues
        from pg_mcp_server.config import get_settings

        settings = get_settings()

        # Verify database settings loaded from custom env
        assert settings.database.host == "custom-host"
        assert settings.database.port == 5433
        assert settings.database.database == "custom_db"
        assert settings.database.user == "custom_user"
        assert settings.database.password.get_secret_value() == "custom_pass"

        # Verify server settings loaded from custom env
        assert settings.server.log_level == "DEBUG"
