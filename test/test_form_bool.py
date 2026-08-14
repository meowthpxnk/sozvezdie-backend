from app.utils.form_bool import parse_form_bool
from app.utils.product_form import (
    parse_flags_is_adult,
    parse_image_slots_payload,
    resolve_is_adult,
)


def test_parse_flags_is_adult():
    assert parse_flags_is_adult('{"is_adult": true}') is True
    assert parse_flags_is_adult('{"is_adult": false}') is False
    assert parse_flags_is_adult("{}") is None


def test_parse_form_bool_truthy_values():
    for value in ("1", "true", "TRUE", "yes", "on", True):
        assert parse_form_bool(value) is True


def test_parse_form_bool_falsy_values():
    for value in ("0", "false", "FALSE", "no", "off", "", False, None):
        assert parse_form_bool(value) is False


def test_parse_image_slots_array_legacy():
    slots, adult = parse_image_slots_payload(
        '[{"type": "existing", "uuid": "abc"}]'
    )
    assert slots == [{"type": "existing", "uuid": "abc"}]
    assert adult is None


def test_parse_image_slots_object_with_adult_flag():
    slots, adult = parse_image_slots_payload(
        '{"slots": [{"type": "new"}], "is_adult": true}'
    )
    assert slots == [{"type": "new"}]
    assert adult is True


def test_resolve_is_adult_true_if_any_channel_is_true():
    assert (
        resolve_is_adult(
            form_value="0",
            query_value="1",
            slots_adult=False,
        )
        is True
    )
    assert (
        resolve_is_adult(
            form_value="false",
            form_adult="1",
            flags_adult=False,
        )
        is True
    )


def test_resolve_is_adult_false_when_all_channels_false():
    assert (
        resolve_is_adult(
            form_value="false",
            query_value="0",
            form_adult="0",
            flags_adult=False,
            slots_adult=False,
        )
        is False
    )


def test_resolve_is_adult_missing_channels_are_false():
    assert resolve_is_adult() is False
