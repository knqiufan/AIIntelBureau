from __future__ import annotations

import pytest

from app.memory import InMemoryGateway
from app.repository import StateRepository
from app.services import BureauService
from app.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(_env_file=None, demo_state_db_path=str(tmp_path / "state.sqlite3"), demo_mode="degrade")


@pytest.fixture
def service(settings):
    return BureauService(settings, InMemoryGateway(), StateRepository(settings.demo_state_db_path))
