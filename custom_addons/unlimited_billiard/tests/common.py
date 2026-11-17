from uuid import uuid4

from odoo import fields


def buka_sesi_kas(env):
    config = env.ref("unlimited_billiard.pos_config_kasir_admin")
    if not config.current_session_id:
        config.open_ui()
    return config.current_session_id


def buat_pesanan_pos(env, lines, partner=None, draft=False, uid=None):
    """Meniru data yang dikirim layar POS (create_from_ui). lines = [(product, qty), ...]."""
    session = buka_sesi_kas(env)
    pricelist = session.config_id.pricelist_id
    order_lines = []
    for product, qty in lines:
        price = pricelist._get_product_price(product, qty)
        order_lines.append((0, 0, {
            "product_id": product.id, "qty": qty, "price_unit": price,
            "price_subtotal": price * qty, "price_subtotal_incl": price * qty,
            "discount": 0, "tax_ids": [(6, 0, [])], "pack_lot_ids": [],
        }))
    total = sum(line[2]["price_subtotal_incl"] for line in order_lines)
    payments = [] if draft else [(0, 0, {
        "amount": total, "name": fields.Datetime.to_string(fields.Datetime.now()),
        "payment_method_id": env.ref("unlimited_billiard.pm_tunai").id,
    })]
    uid = uid or str(uuid4())[:14]
    data = {
        "amount_paid": total if not draft else 0, "amount_return": 0, "amount_tax": 0,
        "amount_total": total, "date_order": fields.Datetime.to_string(fields.Datetime.now()),
        "fiscal_position_id": False, "pricelist_id": pricelist.id, "lines": order_lines,
        "name": "Order %s" % uid, "partner_id": partner and partner.id, "pos_session_id": session.id,
        "sequence_number": 1, "statement_ids": payments, "uid": uid, "user_id": env.user.id,
        "to_invoice": False,
    }
    res = env["pos.order"].create_from_ui([{"data": data, "id": uid, "to_invoice": False}], draft=draft)
    return env["pos.order"].browse(res[0]["id"])
