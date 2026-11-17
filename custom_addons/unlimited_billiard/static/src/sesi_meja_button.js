/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { Component, useState, onWillStart, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { NumberPopup } from "@point_of_sale/app/utils/input_popups/number_popup";
import { ConfirmPopup } from "@point_of_sale/app/utils/confirm_popup/confirm_popup";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

// FR-08: tombol Mulai Sesi / Selesai Sesi pada layar pesanan meja (L-08/L-09).
export class SesiMejaButton extends Component {
    static template = "unlimited_billiard.SesiMejaButton";

    setup() {
        this.pos = usePos();
        this.popup = useService("popup");
        this.orm = useService("orm");
        this.state = useState({ sesi: false, busy: false });
        onWillStart(() => this.refresh());
        const timer = setInterval(() => this.refresh(), 30000);
        onWillUnmount(() => clearInterval(timer));
    }

    get order() {
        return this.pos.get_order();
    }

    get label() {
        const sesi = this.state.sesi;
        if (!sesi) {
            return _t("Mulai Sesi");
        }
        const biaya = this.env.utils.formatCurrency(sesi.biaya_sewa);
        return _t("Selesai Sesi · %s mnt · %s", sesi.durasi_menit, biaya);
    }

    async refresh() {
        if (!this.order?.tableId) {
            return;
        }
        this.state.sesi = await this.orm.call("ub.sesi.meja", "pos_status", [this.order.name, this.order.tableId]);
    }

    async click() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.refresh();
            await (this.state.sesi ? this.selesai() : this.mulai());
        } catch (error) {
            const body = error?.data?.message || error?.message || String(error);
            await this.popup.add(ErrorPopup, { title: _t("Sesi Meja"), body });
        } finally {
            this.state.busy = false;
        }
    }

    async mulai() {
        const { confirmed, payload: jenis } = await this.popup.add(SelectionPopup, {
            title: _t("Mulai sesi %s", this.order.getTable()?.name || ""),
            list: [
                { id: 1, label: _t("Open Table (dihitung per menit)"), item: "open_table", isSelected: true },
                { id: 2, label: _t("Durasi Tetap (paket jam)"), item: "durasi_tetap" },
            ],
        });
        if (!confirmed) {
            return;
        }
        let durasi = 0;
        if (jenis === "durasi_tetap") {
            const res = await this.popup.add(NumberPopup, { title: _t("Durasi dipesan (jam)"), startingValue: 1 });
            if (!res.confirmed) {
                return;
            }
            durasi = parseFloat(res.payload) || 0;
        }
        this.state.sesi = await this.orm.call("ub.sesi.meja", "pos_mulai", [], {
            meja_id: this.order.tableId,
            pos_reference: this.order.name,
            partner_id: this.order.get_partner()?.id || false,
            jenis_tarif: jenis,
            durasi_dipesan: durasi,
        });
    }

    async selesai() {
        const sesi = this.state.sesi;
        const { confirmed } = await this.popup.add(ConfirmPopup, {
            title: _t("Selesai sesi meja?"),
            body: _t("Durasi %s menit, tarif %s, biaya sewa %s. Baris Sewa Meja akan ditambahkan ke pesanan.",
                sesi.durasi_menit, sesi.tarif, this.env.utils.formatCurrency(sesi.biaya_sewa)),
        });
        if (!confirmed) {
            return;
        }
        const hasil = await this.orm.call("ub.sesi.meja", "pos_selesai", [[sesi.id]], {
            meja_id: this.order.tableId,
            pos_reference: this.order.name,
            partner_id: this.order.get_partner()?.id || false,
        });
        const product = this.pos.db.get_product_by_id(hasil.product_id);
        const line = await this.order.add_product(product, { quantity: 1, price: hasil.biaya_sewa, merge: false });
        if (line) {
            line.price_type = "manual"; // jangan dihitung ulang oleh pricelist
            line.set_customer_note(hasil.keterangan); // tercetak di setruk
        }
        this.state.sesi = false;
    }
}

ProductScreen.addControlButton({
    component: SesiMejaButton,
    condition: function () {
        return this.pos.config.module_pos_restaurant;
    },
    position: ["before", "SetPricelistButton"],
});
