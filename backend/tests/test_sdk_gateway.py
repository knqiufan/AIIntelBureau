from __future__ import annotations

from app.domain import AgentId
from app.memory import PowerMemSdkGateway
from app.settings import Settings


class FakeMemory:
    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        self.cards: list[dict] = []

    def add(self, content, *, user_id, agent_id, metadata, infer):
        assert infer is False
        assert agent_id == self.agent_id
        card = {
            "id": f"{agent_id}-{len(self.cards) + 1}",
            "content": content,
            "agent_id": agent_id,
            "metadata": metadata,
            "user_id": user_id,
        }
        self.cards.append(card)
        return card

    def search(self, query, *, user_id, agent_id, limit):
        assert query == "密码"
        assert user_id == "case:sdk-case"
        assert agent_id == self.agent_id
        assert limit == 20
        return list(self.cards)

    def get_all(self, *, user_id, agent_id, limit):
        assert user_id == "case:sdk-case"
        assert agent_id == self.agent_id
        return list(self.cards[:limit])

    def delete(self, memory_id, *, user_id, agent_id):
        assert user_id == "case:sdk-case"
        assert agent_id == self.agent_id
        self.cards = [card for card in self.cards if card["id"] != memory_id]


def _fake_create_memory(monkeypatch):
    created: list[tuple[dict, str]] = []
    memories: dict[str, FakeMemory] = {}

    def create_memory(*, config, agent_id):
        created.append((config, agent_id))
        return memories.setdefault(agent_id, FakeMemory(agent_id))

    monkeypatch.setattr("powermem.create_memory", create_memory)
    return created


def test_direct_sdk_gateway_uses_oceanbase_mysql_compatible_config_and_scope(monkeypatch):
    created = _fake_create_memory(monkeypatch)
    settings = Settings(
        _env_file=None,
        seekdb_mode="oceanbase",
        seekdb_host="seekdb.example.test",
        seekdb_port=2881,
        seekdb_user="root@tenant#cluster",
        seekdb_password="test-password",
        seekdb_database="ai_intel_bureau",
        embedding_api_key="embedding-test-key",
        embedding_model="step-embedding-test",
    )
    gateway = PowerMemSdkGateway(settings)

    card = gateway.write_private("sdk-case", AgentId.INFORMANT, "密码是 0427", topic="password", kind="secret", created_by="script")
    hits = gateway.search_space("sdk-case", AgentId.INFORMANT, "密码")

    assert card.id == "informant-1"
    assert [hit.id for hit in hits] == [card.id]
    config, agent_id = created[0]
    vector_config = config["vector_store"]["config"]
    assert agent_id == "informant"
    assert vector_config["host"] == "seekdb.example.test"
    assert vector_config["port"] == "2881"
    assert vector_config["user"] == "root@tenant#cluster"
    assert vector_config["password"] == "test-password"
    assert vector_config["db_name"] == "ai_intel_bureau"
    assert vector_config["ob_path"] == "./data/seekdb"
    assert "connection_args" not in vector_config
    assert "connect_args" not in vector_config
    assert config["embedder"]["config"]["model"] == "step-embedding-test"


def test_direct_oceanbase_configuration_parses_in_the_powermem_sdk_schema():
    from powermem.configs import MemoryConfig

    settings = Settings(
        _env_file=None,
        seekdb_mode="oceanbase",
        seekdb_host="seekdb.example.test",
        seekdb_port=2881,
        seekdb_user="root@tenant#cluster",
        seekdb_password="test-password",
        seekdb_database="ai_intel_bureau",
        embedding_api_key="embedding-test-key",
        embedding_model="step-embedding-test",
    )

    parsed = MemoryConfig(**settings.powermem_config())
    vector_config = parsed.vector_store.config

    assert vector_config["host"] == "seekdb.example.test"
    assert vector_config["port"] == "2881"
    assert vector_config["user"] == "root@tenant#cluster"
    assert "connection_args" not in vector_config
    assert "connect_args" not in vector_config


def test_openai_compatible_siliconflow_bge_m3_omits_dimensions_override():
    settings = Settings(
        _env_file=None,
        embedding_provider="openai",
        embedding_base_url="https://api.siliconflow.cn/v1",
        embedding_api_key="embedding-test-key",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        embedding_pass_dimensions=False,
    )

    config = settings.powermem_config()

    assert config["embedder"]["provider"] == "openai"
    assert config["embedder"]["config"]["openai_base_url"] == "https://api.siliconflow.cn/v1"
    assert config["embedder"]["config"]["pass_dimensions"] is False
    assert config["vector_store"]["config"]["embedding_model_dims"] == 1024


def test_native_siliconflow_provider_is_configurable_without_dimensions_override():
    settings = Settings(
        _env_file=None,
        embedding_provider="siliconflow",
        embedding_base_url="https://api.siliconflow.cn/v1",
        embedding_api_key="embedding-test-key",
        embedding_model="BAAI/bge-m3",
        embedding_dimensions=1024,
        embedding_pass_dimensions=False,
    )

    config = settings.powermem_config()

    assert config["embedder"]["provider"] == "siliconflow"
    assert config["embedder"]["config"]["siliconflow_base_url"] == "https://api.siliconflow.cn/v1"
    assert "embedding_dims" not in config["embedder"]["config"]


def test_direct_sdk_gateway_uses_empty_host_for_embedded_seekdb(monkeypatch):
    created = _fake_create_memory(monkeypatch)
    settings = Settings(
        _env_file=None,
        seekdb_mode="embedded",
        seekdb_path="./tmp/seekdb",
        embedding_api_key="embedding-test-key",
        embedding_model="step-embedding-test",
    )
    gateway = PowerMemSdkGateway(settings)

    card = gateway.write_private("sdk-case", AgentId.INFORMANT, "密码是 0427", topic="password", kind="secret", created_by="script")

    assert card.id == "informant-1"
    config, agent_id = created[0]
    assert agent_id == "informant"
    assert config["vector_store"]["config"]["host"] == ""
    assert config["vector_store"]["config"]["ob_path"] == "./tmp/seekdb"
    assert "connect_args" not in config["vector_store"]["config"]


def test_warmup_leaves_no_card_in_the_test_gateway(service):
    service.warmup()
    assert service.gateway.list_space("warmup", AgentId.DETECTIVE) == []
