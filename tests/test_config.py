from pathlib import Path

from pytest import MonkeyPatch

from personal_kb_mcp.config import Settings


def test_설정은_명시하지_않은_값에_안전한_기본값을_사용한다(tmp_path: Path) -> None:
    # Given: vault 경로만 명시한 설정이 있다.
    settings = Settings(vault_path=tmp_path / "vault")

    # When: 서버, 쓰기, provenance, vector 기본값을 조회한다.
    observed_defaults = {
        "host": settings.host,
        "port": settings.port,
        "mcp_path": settings.mcp_path,
        "enable_writes": settings.enable_writes,
        "require_if_hash_for_updates": settings.require_if_hash_for_updates,
        "require_provenance": settings.require_provenance,
        "vector_enabled": settings.vector_enabled,
        "vector_provider": settings.vector_provider,
    }

    # Then: 외부 노출과 데이터 손상을 피하는 기본값이 적용된다.
    assert observed_defaults == {
        "host": "127.0.0.1",
        "port": 9999,
        "mcp_path": "/mcp",
        "enable_writes": True,
        "require_if_hash_for_updates": True,
        "require_provenance": True,
        "vector_enabled": False,
        "vector_provider": "none",
    }


def test_설정은_kb_환경변수로_명시한_값을_우선한다(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: KB_ prefix 환경변수로 port, vault, vector provider가 지정되어 있다.
    monkeypatch.setenv("KB_PORT", "10000")
    monkeypatch.setenv("KB_VAULT_PATH", str(tmp_path / "env-vault"))
    monkeypatch.setenv("KB_VECTOR_PROVIDER", "qdrant")

    # When: Settings를 환경변수에서 생성한다.
    settings = Settings()

    # Then: 환경변수 값이 기본값보다 우선 적용된다.
    assert settings.port == 10000
    assert settings.vault_path == tmp_path / "env-vault"
    assert settings.vector_provider == "qdrant"
