from __future__ import annotations

import pytest

from app.memory import InMemoryGateway
from app.repository import StateRepository
from app.services import BureauService
from app.settings import Settings


@pytest.fixture
def settings(tmp_path):
    # Most service tests exercise the explicitly approved local teaching mode.
    # Production keeps free-form audience input disabled by default.
    return Settings(_env_file=None, demo_state_db_path=str(tmp_path / "state.sqlite3"), demo_mode="degrade", demo_allow_freeform_whisper=True, demo_external_data_egress_approved=True)


@pytest.fixture
def service(settings):
    return BureauService(settings, InMemoryGateway(), StateRepository(settings.demo_state_db_path))
