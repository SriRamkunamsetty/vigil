# SPDX-License-Identifier: Apache-2.0
from vigil.privacy.redact import LocalRedactor, pseudonym

R = LocalRedactor()


def test_redacts_common_indian_identifiers():
    text = (
        "Pay ravi@okaxis, PAN ABCDE1234F, IFSC SBIN0001234, call 9876543210, "
        "card 4111 1111 1111 1111, aadhaar 2345 6789 0123, email a.b@example.com"
    )
    out = R.redact(text)
    for secret in [
        "ravi@okaxis",
        "ABCDE1234F",
        "SBIN0001234",
        "9876543210",
        "4111 1111 1111 1111",
        "2345 6789 0123",
        "a.b@example.com",
    ]:
        assert secret not in out.text, secret
    assert out.total >= 7


def test_otp_only_when_context_says_otp():
    assert "482913" not in R.redact("my OTP is 482913").text
    assert "482913" in R.redact("the order number is 482913").text  # not an OTP context


def test_indic_digits_and_non_luhn_numbers():
    assert R.redact("फोन ९८७६५४३२१०").text == "फोन [PHONE]"
    assert R.redact("మీ ఓటీపీ ౪౮౨౯౧౩").text == "మీ ఓటీపీ [OTP]"
    assert R.redact("call me on 98765 43210").text == "call me on [PHONE]"
    out = R.redact("reference 1234 5678 9012 3456")  # fails Luhn: not a card
    assert "card" not in "".join(out.counts)


def test_pseudonym_is_stable_and_not_the_input():
    a, b = pseudonym("user-1"), pseudonym("user-1")
    assert a == b and "user-1" not in a and pseudonym("user-2") != a
