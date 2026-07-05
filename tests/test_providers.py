from regionhop.config import RegionConfig
from regionhop.providers import ProviderError, available_providers, get_provider
from regionhop.providers.manual import ManualProvider


def test_available_providers():
    providers = available_providers()
    assert "manual" in providers
    assert "azure" in providers


def test_get_manual_provider():
    region = RegionConfig(
        name="br",
        provider="manual",
        options={"host": "203.0.113.10", "user": "azureuser", "key_path": "~/.ssh/k"},
    )
    provider = get_provider(region)
    assert isinstance(provider, ManualProvider)
    vm = provider.ensure_running()
    assert vm.host == "203.0.113.10"
    assert vm.user == "azureuser"


def test_unknown_provider_raises():
    region = RegionConfig(name="x", provider="nope", options={})
    try:
        get_provider(region)
    except ProviderError:
        return
    raise AssertionError("expected ProviderError")


def test_manual_requires_host_user():
    region = RegionConfig(name="br", provider="manual", options={"host": "", "user": ""})
    try:
        get_provider(region)
    except ProviderError:
        return
    raise AssertionError("expected ProviderError for missing host/user")


def test_manual_passes_password():
    region = RegionConfig(
        name="br",
        provider="manual",
        options={"host": "h", "user": "u", "password": "pw"},
    )
    vm = get_provider(region).ensure_running()
    assert vm.password == "pw"
    assert vm.key_path is None
