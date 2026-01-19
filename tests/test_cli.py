"""Tests for CLI argument parsing and env file handling."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer
from typer.testing import CliRunner

from pg_mcp_server.__main__ import app, validate_env_file
from pg_mcp_server.config import get_env_file_path, set_env_file_path

runner = CliRunner()


class TestCLI:
    """Tests for CLI using typer's CliRunner."""

    def test_cli_help(self) -> None:
        """Test that --help displays help and includes --env-file option."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--env-file" in result.output
        assert "PATH" in result.output
        assert "PostgreSQL MCP Server" in result.output

    def test_cli_with_env_file_missing(self, tmp_path: Path) -> None:
        """Test CLI with missing env file shows error."""
        missing_file = tmp_path / "missing.env"
        result = runner.invoke(app, ["--env-file", str(missing_file)])
        assert result.exit_code != 0
        assert "Environment file not found" in result.output

    def test_cli_with_env_file_is_directory(self, tmp_path: Path) -> None:
        """Test CLI with directory path shows error."""
        result = runner.invoke(app, ["--env-file", str(tmp_path)])
        assert result.exit_code != 0
        assert "Path is not a file" in result.output


class TestValidateEnvFile:
    """Tests for env file validation callback."""

    def _make_context(self, resilient_parsing: bool = False) -> typer.Context:
        """Create a mock typer.Context for testing."""
        ctx = MagicMock(spec=typer.Context)
        ctx.resilient_parsing = resilient_parsing
        return ctx

    def test_validate_env_file_none(self) -> None:
        """Test validation with None returns None."""
        ctx = self._make_context()
        result = validate_env_file(ctx, None)
        assert result is None

    def test_validate_env_file_valid_file(self, tmp_path: Path) -> None:
        """Test validation with valid file returns resolved path."""
        env_file = tmp_path / "test.env"
        env_file.write_text("PG_HOST=localhost")

        ctx = self._make_context()
        result = validate_env_file(ctx, str(env_file))
        assert result == str(env_file.resolve())

    def test_validate_env_file_missing_file(self, tmp_path: Path) -> None:
        """Test validation with missing file raises BadParameter."""
        missing_file = tmp_path / "missing.env"

        ctx = self._make_context()
        with pytest.raises(typer.BadParameter) as exc_info:
            validate_env_file(ctx, str(missing_file))

        assert "Environment file not found" in str(exc_info.value)

    def test_validate_env_file_directory(self, tmp_path: Path) -> None:
        """Test validation with directory path raises BadParameter."""
        ctx = self._make_context()
        with pytest.raises(typer.BadParameter) as exc_info:
            validate_env_file(ctx, str(tmp_path))

        assert "Path is not a file" in str(exc_info.value)

    def test_validate_env_file_resilient_parsing(self, tmp_path: Path) -> None:
        """Test validation during shell completion returns None."""
        # During shell completion, resilient_parsing is True
        ctx = self._make_context(resilient_parsing=True)
        # Even with a valid path, should return None during completion
        env_file = tmp_path / "test.env"
        env_file.write_text("PG_HOST=localhost")
        result = validate_env_file(ctx, str(env_file))
        assert result is None


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
