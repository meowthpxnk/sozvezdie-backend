from app.integrations.yookassa import YooKassaPaymentResult


def is_payment_successful(payment: YooKassaPaymentResult) -> bool:
    if not payment.paid:
        return False
    return payment.status in ("succeeded", "waiting_for_capture")
