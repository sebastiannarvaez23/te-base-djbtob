from platform.features.communication.messaging.inbox.resource_catalog import (
    SHAREABLE_RESOURCES,
    sync_shareable_resources,
)


class _Manager:
    def __init__(self):
        self.calls = []

    def update_or_create(self, *, code, defaults):
        self.calls.append((code, defaults))
        return object(), True


class _Model:
    def __init__(self):
        self.objects = _Manager()


def test_catalog_starts_without_product_resources():
    assert SHAREABLE_RESOURCES == ()


def test_sync_is_a_noop_until_a_product_registers_resources():
    model = _Model()
    created, updated = sync_shareable_resources(model)
    assert model.objects.calls == []
    assert created == 0
    assert updated == 0
