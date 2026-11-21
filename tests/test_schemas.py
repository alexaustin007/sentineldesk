from sentineldesk.schemas import LabelDistribution, Ticket


def test_label_distribution_exposes_top_two_margin() -> None:
    distribution = LabelDistribution(
        {"Incident": 0.62, "Request": 0.31, "Problem": 0.07}
    )

    assert distribution.label == "Incident"
    assert distribution.confidence == 0.62
    assert distribution.margin == 0.31


def test_ticket_repr_never_contains_raw_customer_text() -> None:
    ticket = Ticket("Private subject", "customer@example.com secret")

    rendered = repr(ticket)

    assert "Private subject" not in rendered
    assert "customer@example.com" not in rendered
