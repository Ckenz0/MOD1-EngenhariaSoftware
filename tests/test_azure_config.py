import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "azure_config.py"


def module():
    spec = importlib.util.spec_from_file_location("azure_config", SCRIPT)
    assert spec and spec.loader
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def inputs():
    return {
        "resourcePrefix": "mod1-demo",
        "environmentName": "mod1-demo-env",
        "registryName": "acrdemo123",
        "vaultName": "kv-demo123",
        "frontendOrigin": "https://demo.azurestaticapps.net",
        "authImage": "acrdemo123.azurecr.io/identity@sha256:" + "a" * 64,
        "projectsImage": "acrdemo123.azurecr.io/projects@sha256:" + "b" * 64,
        "backlogImage": "acrdemo123.azurecr.io/backlog@sha256:" + "c" * 64,
        "authDatabaseSecretUri": "https://kv-demo123.vault.azure.net/secrets/identity-database-url/"
        + "1" * 32,
        "projectsDatabaseSecretUri": "https://kv-demo123.vault.azure.net/secrets/projects-database-url/"
        + "2" * 32,
        "backlogDatabaseSecretUri": "https://kv-demo123.vault.azure.net/secrets/backlog-database-url/"
        + "3" * 32,
        "jwtKeySecretUri": "https://kv-demo123.vault.azure.net/secrets/identity-jwt-private-key/"
        + "4" * 32,
    }


def test_render_app_parameters_contains_only_expected_public_references(tmp_path):
    api = module()
    source = inputs()
    path = tmp_path / "params.json"
    api.write_parameters(source, path)
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["parameters"]["authImage"]["value"].endswith("@sha256:" + "a" * 64)
    assert result["parameters"]["frontendOrigin"]["value"] == "https://demo.azurestaticapps.net"
    assert set(result["parameters"]) == set(source)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("frontendOrigin", "http://example.com"),
        ("frontendOrigin", "https://user:password@example.com"),
        ("frontendOrigin", "https://example.com/path"),
        ("frontendOrigin", "https://example.com?token=secret"),
        ("frontendOrigin", "https://example.com/#fragment"),
        ("frontendOrigin", "https://example.com\\@evil.test"),
        ("frontendOrigin", "https://example.com\n"),
        ("authImage", "acrdemo123.azurecr.io/identity:latest"),
        ("authImage", "evil.azurecr.io/identity@sha256:" + "a" * 64),
        ("authImage", "acrdemo123.azurecr.io/identity@sha256:short"),
        ("resourcePrefix", "x; echo injection"),
        ("registryName", "INVALID_NAME"),
        ("jwtKeySecretUri", "https://kv-demo123.vault.azure.net/secrets/identity-jwt-private-key"),
        (
            "jwtKeySecretUri",
            "https://other.vault.azure.net/secrets/identity-jwt-private-key/" + "4" * 32,
        ),
        (
            "authDatabaseSecretUri",
            "https://kv-demo123.vault.azure.net/secrets/backlog-database-url/" + "1" * 32,
        ),
    ],
)
def test_reject_invalid_or_cross_service_references_without_replacing_output(tmp_path, key, value):
    api = module()
    source = inputs()
    source[key] = value
    path = tmp_path / "params.json"
    path.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError):
        api.write_parameters(source, path)
    assert path.read_text(encoding="utf-8") == "existing"


def test_reject_unknown_parameters_and_do_not_echo_values(tmp_path):
    api = module()
    source = inputs() | {"DATABASE_URL": "private-credential"}
    with pytest.raises(ValueError) as exc:
        api.write_parameters(source, tmp_path / "params.json")
    assert "private-credential" not in str(exc.value)
