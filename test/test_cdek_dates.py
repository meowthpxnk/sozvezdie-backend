from datetime import date, timedelta

from app.integrations import cdek


def test_build_available_dates_from_cdek_range():
    today = date.today()
    d_min = today + timedelta(days=3)
    d_max = today + timedelta(days=7)
    dates = cdek.build_available_dates(
        1,
        3,
        delivery_date_min=d_min,
        delivery_date_max=d_max,
    )
    assert dates == [
        (d_min + timedelta(days=i)).isoformat() for i in range((d_max - d_min).days + 1)
    ]


def test_is_delivery_date_available_uses_range():
    today = date.today()
    d_min = today + timedelta(days=2)
    d_max = today + timedelta(days=5)
    assert cdek.is_delivery_date_available(
        d_min,
        delivery_date_min=d_min,
        delivery_date_max=d_max,
        period_min=2,
        period_max=5,
    )
    assert not cdek.is_delivery_date_available(
        d_min - timedelta(days=1),
        delivery_date_min=d_min,
        delivery_date_max=d_max,
        period_min=2,
        period_max=5,
    )


def test_format_shipment_datetime_cdek_offset():
    assert cdek.format_shipment_datetime(date(2026, 6, 1)) == "2026-06-01T10:00:00+0300"


def test_extract_delivery_date_range_from_tariff_item():
    item = {
        "tariff_code": 136,
        "delivery_sum": 350.0,
        "period_min": 2,
        "period_max": 4,
        "delivery_date_range": {"min": "2026-06-01", "max": "2026-06-10"},
    }
    result = cdek._tariff_item_to_result(item)
    assert result.delivery_date_min == date(2026, 6, 1)
    assert result.delivery_date_max == date(2026, 6, 10)
