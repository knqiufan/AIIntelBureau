from app.clear_demo_data import inspect_clear_plan
from app.domain import AgentId


def test_clear_plan_only_counts_case_scoped_power_mem_cards(service):
    first = service.create_case().case
    first_loaded = service.load_script(first.case_id, "password", first.version)
    second = service.create_case().case
    service.load_script(second.case_id, "allergy", second.version)

    plan = inspect_clear_plan(service.repository, service.gateway)

    assert plan.case_count == 2
    assert plan.remote_card_count == 6
    assert plan.remote_error is None

    service.clear_ephemeral_data()
    assert service.repository.case_ids() == []
    assert service.gateway.list_space(first_loaded.case.case_id, AgentId.INFORMANT) == []
