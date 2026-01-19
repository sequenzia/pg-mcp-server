"""Tests for CLI argument parsing and env file handling."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from pg_mcp_server.__main__ import app, resolve_default_env_file, validate_env_file
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

    def test_cli_auto_loads_env_from_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI auto-loads .env from cwd when --env-file not specified."""
        # Create .env file in tmp_path
        env_file = tmp_path / ".env"
        env_file.write_text(
            "PG_HOST=auto-loaded-host\n"
            "PG_DATABASE=testdb\n"
            "PG_USER=testuser\n"
            "PG_PASSWORD=testpass\n"
        )

        # Change cwd to tmp_path
        monkeypatch.chdir(tmp_path)

        with patch("pg_mcp_server.__main__.create_engine") as mock_create, patch(
            "pg_mcp_server.__main__.test_connection"
        ), patch("pg_mcp_server.__main__.dispose_engine"):
            mock_create.return_value = AsyncMock()

            # Run without --env-file flag
            result = runner.invoke(app, ["test"])

            assert result.exit_code == 0
            # Verify settings were loaded from auto-detected .env
            call_args = mock_create.call_args[0][0]
            assert call_args.host == "auto-loaded-host"

    def test_cli_works_without_env_file_in_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test CLI proceeds without error when no .env in cwd and no --env-file."""
        # tmp_path has no .env file, but set required env vars
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PG_HOST", "env-var-host")
        monkeypatch.setenv("PG_DATABASE", "testdb")
        monkeypatch.setenv("PG_USER", "testuser")
        monkeypatch.setenv("PG_PASSWORD", "testpass")

        with patch("pg_mcp_server.__main__.create_engine") as mock_create, patch(
            "pg_mcp_server.__main__.test_connection"
        ), patch("pg_mcp_server.__main__.dispose_engine"):
            mock_create.return_value = AsyncMock()

            # Run without --env-file flag and no .env in cwd
            result = runner.invoke(app, ["test"])

            assert result.exit_code == 0
            # Verify settings were loaded from environment variables
            call_args = mock_create.call_args[0][0]
            assert call_args.host == "env-var-host"


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


class TestResolveDefaultEnvFile:
    """Tests for auto-detection of .env file in current working directory."""

    def test_returns_explicit_path_unchanged(self, tmp_path: Path) -> None:
        """Test that explicitly provided path is returned unchanged."""
        env_file = tmp_path / "custom.env"
        env_file.write_text("PG_HOST=localhost")
        result = resolve_default_env_file(str(env_file))
        assert result == str(env_file)

    def test_detects_env_file_in_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that .env file in cwd is detected when no explicit path provided."""
        # Create .env file in tmp_path
        env_file = tmp_path / ".env"
        env_file.write_text("PG_HOST=localhost")

        # Change cwd to tmp_path
        monkeypatch.chdir(tmp_path)

        result = resolve_default_env_file(None)
        assert result == str(env_file.resolve())

    def test_returns_none_when_no_env_file_in_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that None is returned when no .env file exists in cwd."""
        # tmp_path has no .env file
        monkeypatch.chdir(tmp_path)

        result = resolve_default_env_file(None)
        assert result is None

    def test_returns_none_when_env_is_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that None is returned when .env exists but is a directory."""
        # Create .env as a directory
        env_dir = tmp_path / ".env"
        env_dir.mkdir()

        monkeypatch.chdir(tmp_path)

        result = resolve_default_env_file(None)
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


class TestTestCommand:
    """Tests for the 'test' CLI command."""

    def test_test_command_success(self, tmp_path: Path) -> None:
        """Test successful connection test exits with code 0."""
        # Create env file with test values
        env_file = tmp_path / "test.env"
        env_file.write_text(
            "PG_HOST=localhost\n"
            "PG_DATABASE=testdb\n"
            "PG_USER=testuser\n"
            "PG_PASSWORD=testpass\n"
        )

        with patch("pg_mcp_server.__main__.create_engine") as mock_create, patch(
            "pg_mcp_server.__main__.test_connection"
        ) as mock_test, patch("pg_mcp_server.__main__.dispose_engine") as mock_dispose:
            mock_engine = AsyncMock()
            mock_create.return_value = mock_engine
            mock_test.return_value = None
            mock_dispose.return_value = None

            # --env-file is now at root level, before subcommand
            result = runner.invoke(app, ["--env-file", str(env_file), "test"])

            assert result.exit_code == 0
            assert "Connection successful" in result.output
            mock_create.assert_called_once()
            mock_test.assert_called_once_with(mock_engine)
            mock_dispose.assert_called_once_with(mock_engine)

    def test_test_command_failure(self, tmp_path: Path) -> None:
        """Test failed connection test exits with code 1."""
        env_file = tmp_path / "test.env"
        env_file.write_text(
            "PG_HOST=localhost\n"
            "PG_DATABASE=testdb\n"
            "PG_USER=testuser\n"
            "PG_PASSWORD=testpass\n"
        )

        with patch("pg_mcp_server.__main__.create_engine") as mock_create, patch(
            "pg_mcp_server.__main__.test_connection"
        ) as mock_test, patch("pg_mcp_server.__main__.dispose_engine") as mock_dispose:
            mock_engine = AsyncMock()
            mock_create.return_value = mock_engine
            mock_test.side_effect = Exception("Connection refused")
            mock_dispose.return_value = None

            # --env-file is now at root level, before subcommand
            result = runner.invoke(app, ["--env-file", str(env_file), "test"])

            assert result.exit_code == 1
            assert "Connection failed" in result.output
            assert "Connection refused" in result.output

    def test_test_command_with_env_file_option(self, tmp_path: Path) -> None:
        """Test that --env-file option works with test command."""
        env_file = tmp_path / "custom.env"
        env_file.write_text(
            "PG_HOST=custom-host\n"
            "PG_DATABASE=custom_db\n"
            "PG_USER=custom_user\n"
            "PG_PASSWORD=custom_pass\n"
        )

        with patch("pg_mcp_server.__main__.create_engine") as mock_create, patch(
            "pg_mcp_server.__main__.test_connection"
        ), patch("pg_mcp_server.__main__.dispose_engine"):
            mock_create.return_value = AsyncMock()

            # --env-file is now at root level, before subcommand
            result = runner.invoke(app, ["--env-file", str(env_file), "test"])

            assert result.exit_code == 0
            # Verify settings were loaded with custom host
            call_args = mock_create.call_args[0][0]
            assert call_args.host == "custom-host"

    def test_test_command_help(self) -> None:
        """Test that test command help is displayed."""
        result = runner.invoke(app, ["test", "--help"])
        assert result.exit_code == 0
        assert "Test database connection" in result.output
        # --env-file is now at root level, not on test subcommand
