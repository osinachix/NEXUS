import main


def test_resolve_model_name_defaults_when_env_var_absent():
    assert main.resolve_model_name({}) == main.DEFAULT_MODEL


def test_resolve_model_name_honors_env_override():
    overridden = "anthropic:claude-3-7-sonnet-20250219"
    assert main.resolve_model_name({"ANTHROPIC_MODEL": overridden}) == overridden


def test_default_model_is_pinned_not_floating():
    # A floating "-latest" alias breaks reproducibility; Phase 0 requires a
    # dated snapshot instead.
    assert "latest" not in main.DEFAULT_MODEL
