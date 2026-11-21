from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_streamlit_dashboard_runs_end_to_end() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py").run(timeout=30)

    app.text_input[0].set_value("Forgot my password")
    app.text_area[0].set_value(
        "I forgot my password for the customer portal and the reset email never arrives."
    )
    app.button[0].click().run(timeout=30)

    assert not app.exception
    assert any("Verified draft ready" in message.value for message in app.success)
    assert [heading.value for heading in app.subheader] == [
        "1. Independent classification and RAG evidence",
        "2. Decision engine",
        "3. Retrieved historical evidence",
        "4. Grounded draft and independent verifier",
        "5. Measured execution",
    ]


def test_judge_mode_refuses_silent_mock_fallbacks() -> None:
    app = AppTest.from_file(PROJECT_ROOT / "app.py").run(timeout=30)

    app.toggle[0].set_value(True).run(timeout=30)

    assert not app.exception
    assert any("artifacts are missing" in message.value for message in app.error)
