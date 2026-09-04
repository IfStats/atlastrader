from packages.core.enums import SignalDirection
from packages.engine.decision import DecisionEngine
from packages.engine.opportunity import Opportunity


def make_opportunity(
    *,
    direction: SignalDirection = SignalDirection.LONG,
    score: float = 0.70,
    confidence: float = 0.80,
    eligible: bool = True,
    rejection_reasons: list[str] | None = None,
) -> Opportunity:
    return Opportunity(
        symbol="XAUUSD",
        direction=direction,
        score=score,
        confidence=confidence,
        eligible=eligible,
        rationale=["test_opportunity"],
        rejection_reasons=rejection_reasons or [],
    )


def test_strong_eligible_opportunity_is_approved() -> None:
    engine = DecisionEngine()

    decision = engine.decide(make_opportunity())

    assert decision.approved is True
    assert decision.decision is SignalDirection.LONG
    assert decision.score == 0.70
    assert decision.confidence == 0.80
    assert decision.rejection_reasons == []


def test_strong_short_opportunity_is_approved() -> None:
    engine = DecisionEngine()

    decision = engine.decide(
        make_opportunity(
            direction=SignalDirection.SHORT,
            score=0.70,
            confidence=0.80,
        )
    )

    assert decision.approved is True
    assert decision.decision is SignalDirection.SHORT


def test_ineligible_opportunity_is_rejected() -> None:
    engine = DecisionEngine()

    decision = engine.decide(
        make_opportunity(
            eligible=False,
            rejection_reasons=["event_risk_above_threshold:0.700"],
        )
    )

    assert decision.approved is False
    assert decision.decision is SignalDirection.FLAT
    assert "event_risk_above_threshold:0.700" in decision.rejection_reasons


def test_ineligible_opportunity_without_reason_gets_default_reason() -> None:
    engine = DecisionEngine()

    decision = engine.decide(
        make_opportunity(
            eligible=False,
        )
    )

    assert decision.approved is False
    assert decision.decision is SignalDirection.FLAT
    assert "opportunity_not_eligible" in decision.rejection_reasons


def test_low_score_is_rejected() -> None:
    engine = DecisionEngine(minimum_score=0.30)

    decision = engine.decide(
        make_opportunity(score=0.20)
    )

    assert decision.approved is False
    assert decision.decision is SignalDirection.FLAT
    assert "score_below_threshold:0.300" in decision.rejection_reasons


def test_low_confidence_is_rejected() -> None:
    engine = DecisionEngine(minimum_confidence=0.50)

    decision = engine.decide(
        make_opportunity(confidence=0.40)
    )

    assert decision.approved is False
    assert decision.decision is SignalDirection.FLAT
    assert "confidence_below_threshold:0.500" in decision.rejection_reasons


def test_multiple_rejection_reasons_are_preserved() -> None:
    engine = DecisionEngine(
        minimum_score=0.80,
        minimum_confidence=0.90,
    )

    decision = engine.decide(
        make_opportunity(
            score=0.40,
            confidence=0.30,
            eligible=False,
            rejection_reasons=["technical_intelligence_conflict"],
        )
    )

    assert decision.approved is False
    assert decision.decision is SignalDirection.FLAT
    assert "technical_intelligence_conflict" in decision.rejection_reasons
    assert "score_below_threshold:0.800" in decision.rejection_reasons
    assert "confidence_below_threshold:0.900" in decision.rejection_reasons


def test_constructor_rejects_invalid_thresholds() -> None:
    invalid_values = (
        ("minimum_score", -0.01),
        ("minimum_score", 1.01),
        ("minimum_confidence", -0.01),
        ("minimum_confidence", 1.01),
    )

    for parameter, value in invalid_values:
        try:
            DecisionEngine(**{parameter: value})
        except ValueError as exc:
            assert parameter in str(exc)
        else:
            raise AssertionError(
                f"Expected ValueError for {parameter}={value}"
            )