"""The authority model: competence, limit, reporting line, delegation ceiling.

Each test pins one of the four rules in ``apps/iam/authority.py``, and the first
two pin defects that were live on ``staging``: a driver could approve a payroll
run of forty-eight million francs (D18), and the approvals inbox gated on two
permission codes that were never seeded, so no ordinary user could approve
anything at all (D19).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from apps.approvals import services
from apps.approvals.models import ApprovalRequest
from apps.iam import authority
from apps.iam.models import Organization, Permission, Role, User

pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.create(name="Remera Pharmacy", type="RETAIL")


def person(username, org, *role_codes, reports_to=None, limit=None):
    user = User.objects.create_user(
        username=username, password="pw", email=f"{username}@umoja.rw", organization=org
    )
    for code in role_codes:
        user.roles.add(Role.objects.get(code=code))
    if reports_to is not None:
        user.reports_to = reports_to
    if limit is not None:
        user.approval_limit = limit
    user.save()
    return user


def payroll(org, requester, amount="48000000"):
    return services.request_approval(
        resource_type="hr.payroll_run",
        resource_id="1",
        organization=org,
        requested_by=requester,
        payload={"net_pay": amount},
        reason=f"August payroll — RWF {amount}",
    )


# ---------------------------------------------------------------------------
# R1 — rank never grants competence
# ---------------------------------------------------------------------------


def test_a_driver_cannot_approve_the_payroll(org):
    """D18. This passed before F2: claim() checked only that it was not your own."""
    hr = person("sarah_hr", org, "HR_MANAGER")
    driver = person("moses_driver", org, "DRIVER")

    with pytest.raises(services.ApprovalError) as exc:
        services.claim(approval=payroll(org, hr), user=driver)
    assert "user.manage" in str(exc.value)


def test_a_cashier_cannot_approve_the_payroll(org):
    hr = person("sarah_hr", org, "HR_MANAGER")
    cashier = person("aline_cashier", org, "CASHIER")
    with pytest.raises(services.ApprovalError):
        services.claim(approval=payroll(org, hr), user=cashier)


def test_a_branch_manager_cannot_dispense_however_senior(org):
    """The rule the brief states: seniority is not a licence.

    A branch manager supervises the pharmacist and cannot do their job — Rwanda
    FDA rules attach to the licence, not the job title.
    """
    manager = person("claire_boss", org, "BRANCH_MANAGER")
    pharmacist = person("jean_pharmacist", org, "PHARMACIST", reports_to=manager)

    assert pharmacist.has_permission("sale.dispense")
    assert not manager.has_permission(
        "sale.dispense"
    ), "rank must not confer a competence the role was never granted"
    # And the manager holds oversight the pharmacist does not.
    assert manager.has_permission("audit.view")
    assert not pharmacist.has_permission("audit.view")


def test_an_auditor_can_see_everything_and_change_nothing(org):
    auditor = person("inspector", org, "AUDITOR")
    for code in ("catalog.view", "inventory.view", "finance.view", "audit.view"):
        assert auditor.has_permission(code)
    for code in ("sale.create", "inventory.adjust", "finance.manage", "user.manage"):
        assert not auditor.has_permission(code)


# ---------------------------------------------------------------------------
# R2 — the ceiling
# ---------------------------------------------------------------------------


def test_the_right_competence_is_still_capped_by_the_limit(org):
    """An HR manager may decide payroll — but not one of any size."""
    boss = person("ceo", org, "ORG_ADMIN")
    hr = person("sarah_hr", org, "HR_MANAGER", reports_to=boss)
    other_hr = person("frank_hr", org, "HR_MANAGER", reports_to=boss)

    # HR_MANAGER's seeded ceiling is 3,000,000.
    assert authority.approval_limit(hr) == Decimal("3000000")

    small = services.claim(approval=payroll(org, hr, "250000"), user=other_hr)
    assert small.claimed_by_id == other_hr.pk

    with pytest.raises(services.ApprovalError) as exc:
        services.claim(approval=payroll(org, hr, "48000000"), user=other_hr)
    assert "above your approval limit" in str(exc.value)


def test_a_personal_override_beats_the_role(org):
    """How a deputy is covered for a fortnight without being handed a role."""
    boss = person("ceo", org, "ORG_ADMIN")
    hr = person("sarah_hr", org, "HR_MANAGER", reports_to=boss)
    deputy = person("deputy_hr", org, "HR_MANAGER", limit=Decimal("60000000"))

    assert authority.approval_limit(deputy) == Decimal("60000000")
    assert services.claim(approval=payroll(org, hr), user=deputy).claimed_by_id == deputy.pk


def test_the_highest_role_limit_applies_when_someone_holds_two(org):
    both = person("dual", org, "CASHIER", "HR_MANAGER")
    assert authority.approval_limit(both) == Decimal(
        "3000000"
    ), "holding an extra role must never reduce what someone may approve"


def test_an_unlimited_role_has_no_ceiling(org):
    boss = person("ceo", org, "ORG_ADMIN")
    assert authority.approval_limit(boss) is None
    assert authority.within_limit(boss, Decimal("999000000"))


# ---------------------------------------------------------------------------
# R3 — escalation walks the reporting line
# ---------------------------------------------------------------------------


def test_a_blocked_approver_is_told_who_can_do_it(org):
    """A queue that refuses without saying who *can* just sends people hunting."""
    ceo = person("ceo", org, "ORG_ADMIN")
    manager = person("claire_boss", org, "BRANCH_MANAGER", reports_to=ceo)
    hr = person("sarah_hr", org, "HR_MANAGER", reports_to=manager)
    other_hr = person("frank_hr", org, "HR_MANAGER", reports_to=manager)

    check = services.authority_for(approval=payroll(org, hr), user=other_hr)
    assert not check.allowed
    # The branch manager holds no user.manage, so the chain skips them.
    assert [u.username for u in check.escalate_to] == ["ceo"]


def test_the_escalation_chain_is_ordered_nearest_first(org):
    ceo = person("ceo", org, "ORG_ADMIN")
    manager = person("claire_boss", org, "BRANCH_MANAGER", reports_to=ceo)
    clerk = person("aline_cashier", org, "CASHIER", reports_to=manager)
    assert [u.username for u in authority.escalation_chain(clerk)] == ["claire_boss", "ceo"]


def test_a_cycle_in_the_reporting_line_does_not_hang(org):
    a = person("a", org, "CASHIER")
    b = person("b", org, "CASHIER", reports_to=a)
    a.reports_to = b
    a.save()
    assert [u.username for u in authority.escalation_chain(a)] == ["b"]


def test_a_manager_sees_their_whole_team(org):
    ceo = person("ceo", org, "ORG_ADMIN")
    manager = person("claire_boss", org, "BRANCH_MANAGER", reports_to=ceo)
    person("aline_cashier", org, "CASHIER", reports_to=manager)
    person("jean_pharmacist", org, "PHARMACIST", reports_to=manager)

    assert len(authority.reports_of(manager)) == 2
    assert len(authority.reports_of(ceo)) == 1
    assert len(authority.reports_of(ceo, recursive=True)) == 3


# ---------------------------------------------------------------------------
# R4 — you cannot give away what you do not hold
# ---------------------------------------------------------------------------


def test_you_cannot_reassign_an_approval_you_could_not_decide(org):
    """Otherwise reassignment is the way round every other rule."""
    ceo = person("ceo", org, "ORG_ADMIN")
    manager = person("claire_boss", org, "BRANCH_MANAGER", reports_to=ceo)
    hr = person("sarah_hr", org, "HR_MANAGER")
    other_hr = person("frank_hr", org, "HR_MANAGER", limit=Decimal("99000000"))

    # The manager holds approval.manage but not user.manage.
    with pytest.raises(services.ApprovalError) as exc:
        services.reassign(approval=payroll(org, hr), to_user=other_hr, by=manager)
    assert "do not hold" in str(exc.value)

    # The CEO can, and the recipient is competent and within limit.
    assert (
        services.reassign(approval=payroll(org, hr), to_user=other_hr, by=ceo).claimed_by_id
        == other_hr.pk
    )


def test_you_cannot_reassign_to_someone_who_cannot_decide_it(org):
    ceo = person("ceo", org, "ORG_ADMIN")
    hr = person("sarah_hr", org, "HR_MANAGER")
    driver = person("moses_driver", org, "DRIVER")
    with pytest.raises(services.ApprovalError):
        services.reassign(approval=payroll(org, hr), to_user=driver, by=ceo)


# ---------------------------------------------------------------------------
# D19 — the inbox permissions exist at all
# ---------------------------------------------------------------------------


def test_the_approval_permissions_are_seeded():
    """approvals/views.py gates on these two; neither was ever created."""
    for code in ("approval.decide", "approval.manage"):
        assert Permission.objects.filter(code=code).exists(), f"{code} is not seeded"


def test_the_roles_that_run_a_branch_can_use_the_inbox(org):
    for code in ("BRANCH_MANAGER", "ACCOUNTANT", "HR_MANAGER", "PHARMACIST"):
        assert person(f"u_{code}", org, code).has_permission("approval.decide")


def test_only_senior_oversight_may_reassign(org):
    assert person("m", org, "BRANCH_MANAGER").has_permission("approval.manage")
    assert not person("a", org, "ACCOUNTANT").has_permission("approval.manage")


def test_the_missing_roles_now_exist():
    """D8/D9 — PROCUREMENT_OFFICER gated a whole app and was not a role."""
    for code in ("BRANCH_MANAGER", "PROCUREMENT_OFFICER", "AUDITOR"):
        assert Role.objects.filter(code=code).exists()


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------


def test_an_unregistered_resource_type_is_not_open_to_everyone(org):
    """A new approval kind nobody remembered to register must fail closed."""
    assert authority.required_permission_for("some.new.thing") == "organization.manage"
    cashier = person("aline_cashier", org, "CASHIER")
    assert not authority.can_decide(user=cashier, resource_type="some.new.thing").allowed


def test_the_amount_is_read_from_the_registered_field():
    assert authority.amount_from_payload("hr.payroll_run", {"net_pay": "1200"}) == Decimal("1200")
    assert authority.amount_from_payload("hr.payroll_run", {"amount": "900"}) == Decimal("900")
    assert authority.amount_from_payload("hr.payroll_run", {}) is None


def test_no_amount_means_competence_alone_decides(org):
    """A limit cannot gate what has no number attached."""
    hr = person("sarah_hr", org, "HR_MANAGER")
    other = person("frank_hr", org, "HR_MANAGER")
    request = services.request_approval(
        resource_type="hr.employee_termination",
        resource_id="7",
        organization=org,
        requested_by=hr,
        payload={},
    )
    assert services.claim(approval=request, user=other).claimed_by_id == other.pk


def test_self_approval_is_still_refused_first(org):
    """Ordering: the self-approval check fires before the authority check.

    The pharmacy is staffed on purpose. A MICRO organisation with nobody else
    holding the competence is now *allowed* to self-approve — refusing there
    produces no second approver, only a pharmacy that cannot run its own
    payroll. This test is about which refusal comes first when a second person
    does exist, so it makes sure one does.
    """
    org.size = Organization.Size.MEDIUM
    org.save(update_fields=["size"])
    hr = person("sarah_hr", org, "HR_MANAGER", limit=Decimal("99000000"))
    person("frank_hr", org, "HR_MANAGER", limit=Decimal("99000000"))
    with pytest.raises(services.ApprovalError) as exc:
        services.claim(approval=payroll(org, hr, "100"), user=hr)
    assert "self-approval" in str(exc.value)


def test_authority_is_rechecked_at_the_moment_of_decision(org):
    """A role can change while an item sits in a queue."""
    hr = person("sarah_hr", org, "HR_MANAGER")
    other = person("frank_hr", org, "HR_MANAGER")
    request = payroll(org, hr, "100000")
    services.claim(approval=request, user=other)

    other.roles.clear()  # demoted after claiming
    with pytest.raises(services.ApprovalError):
        services.decide(approval=request, user=other, approve=True)
    assert ApprovalRequest.objects.get(pk=request.pk).status == ApprovalRequest.Status.PENDING
