from app.policy import detect_script, hold_reason, in_quiet_hours, keyword_reply
from datetime import datetime
from zoneinfo import ZoneInfo


def test_money_is_held():
    assert hold_reason("please pay 500 on upi") == "money"


def test_otp_is_held():
    assert hold_reason("send the otp") == "secret or one-time code"


def test_plain_hello_is_not_held():
    assert hold_reason("hello, reached?") is None


def test_keyword_rule():
    rules = {"keywords": [{"match": ["brochure"], "reply": "I will send the brochure."}]}
    assert keyword_reply("need the brochure", rules).startswith("I will send")


def test_script_detection():
    assert detect_script("क्या हाल है") == "hi"
    assert detect_script("bhai kal milte hai") == "hinglish"
    assert detect_script("see you tomorrow") == "en"


def test_quiet_hours_wraps_midnight():
    late = datetime(2026, 10, 6, 23, 30, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert in_quiet_hours(late) is True
