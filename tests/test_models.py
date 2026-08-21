from db.models import Event, Evidence, WorkOrder


def test_work_order_state_covers_architecture_fields():
    cols = set(WorkOrder.__table__.columns.keys())
    # architecture doc section 12
    expected = {
        "id",
        "project_id",
        "repository",
        "baseline_commit",
        "original_request",
        "confirmed_requirement",
        "acceptance_criteria",
        "worker_runtime_id",
        "worker_thread_id",
        "worker_status",
        "candidate_commit",
        "inspector_runtime_id",
        "inspector_thread_id",
        "inspector_status",
        "inspector_verdict",
        "findings",
        "testing",
        "deployment_status",
        "deployment_id",
        "deployment_url",
        "docs_url",
        "deployment_health",
        "gaps",
        "artifacts",
        "overall_status",
    }
    assert expected <= cols


def test_audit_and_evidence_models_exist():
    assert Evidence.__tablename__ == "evidence"
    assert Event.__tablename__ == "events"
