"""journal.find_unacked: returns pending entries with no matching ack."""
import pytest


def test_find_unacked_empty(_isolated_data_dir):
    import journal
    assert journal.find_unacked() == []


def test_pending_complete_without_ack_is_unacked(_isolated_data_dir):
    import journal
    journal.append("pending_complete", job_id="j1", kbs_reference="REF-1")
    out = journal.find_unacked()
    assert len(out) == 1
    assert out[0]["job_id"] == "j1"
    assert out[0]["kbs_reference"] == "REF-1"


def test_pending_complete_with_ack_is_clean(_isolated_data_dir):
    import journal
    journal.append("pending_complete", job_id="j1", kbs_reference="REF-1")
    journal.append("complete_ack", job_id="j1")
    assert journal.find_unacked() == []


def test_pending_fail_without_ack_is_unacked(_isolated_data_dir):
    import journal
    journal.append("pending_fail", job_id="j2", retry=True, error="boom")
    out = journal.find_unacked()
    assert len(out) == 1
    assert out[0]["event"] == "pending_fail"
    assert out[0]["retry"] is True


def test_multiple_jobs_partial_ack(_isolated_data_dir):
    import journal
    journal.append("pending_complete", job_id="a", kbs_reference="RA")
    journal.append("complete_ack", job_id="a")
    journal.append("pending_complete", job_id="b", kbs_reference="RB")
    journal.append("pending_fail", job_id="c", retry=False, error="x")
    out = {r["job_id"]: r for r in journal.find_unacked()}
    assert set(out.keys()) == {"b", "c"}


def test_ack_only_pops_matching_pending_event(_isolated_data_dir):
    """A fail_ack must NOT clear a pending_complete and vice-versa."""
    import journal
    journal.append("pending_complete", job_id="z", kbs_reference="RZ")
    journal.append("fail_ack", job_id="z", will_retry=False)  # mismatched ack
    out = journal.find_unacked()
    assert len(out) == 1
    assert out[0]["event"] == "pending_complete"


def test_replayed_then_re_pended_is_unacked_again(_isolated_data_dir):
    """If after an ack the worker writes a new pending, it should re-appear."""
    import journal
    journal.append("pending_complete", job_id="r", kbs_reference="X")
    journal.append("complete_ack", job_id="r")
    journal.append("pending_complete", job_id="r", kbs_reference="Y")
    out = journal.find_unacked()
    assert len(out) == 1
    assert out[0]["kbs_reference"] == "Y"
