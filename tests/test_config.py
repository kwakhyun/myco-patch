from mycopatch.core.config import load_config
from mycopatch.core.paths import ensure_myco_layout


def test_init_creates_default_config(tmp_path):
    paths = ensure_myco_layout(tmp_path)

    assert paths.config.exists()
    config = load_config(tmp_path)
    assert config.default_provider == "offline"
    assert config.model_name == "offline-heuristic"
    assert not config.allow_network_for_model_provider
    assert not config.allow_project_test_commands


def test_load_config_overrides_defaults(tmp_path):
    paths = ensure_myco_layout(tmp_path)
    paths.config.write_text(
        """
default_provider = "local-http"
model_name = "local-test-model"
max_input_tokens = 100
max_output_tokens = 50
max_cost_usd = 0.25
allow_network_for_model_provider = true
allow_project_test_commands = true
provider_base_url = "http://127.0.0.1:11434/test"
api_key_env = "MYCO_TEST_KEY"
""",
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.default_provider == "local-http"
    assert config.model_name == "local-test-model"
    assert config.max_input_tokens == 100
    assert config.max_output_tokens == 50
    assert config.max_cost_usd == 0.25
    assert config.allow_network_for_model_provider
    assert config.allow_project_test_commands
