/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { onWillStart, onWillUnmount } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { FloorScreen } from "@pos_restaurant/app/floor_screen/floor_screen";
import { Table } from "@pos_restaurant/app/floor_screen/table";

// FR-08 / L-08: status meja diturunkan dari sesi meja aktif (pos.ubSesiMeja = {meja_id: sesi}).
const WARNA = {
    berjalan: { background: "#ffb700", text: "#002b50" },
    melewati_batas: { background: "#dc3545", text: "white" },
};

patch(FloorScreen.prototype, {
    setup() {
        super.setup(...arguments);
        const muat = async () => {
            this.pos.ubSesiMeja = await this.orm.call("ub.sesi.meja", "pos_status_meja", []);
        };
        onWillStart(muat);
        const timer = setInterval(muat, 30000);
        onWillUnmount(() => clearInterval(timer));
    },
});

patch(Table.prototype, {
    get ubSesi() {
        return this.pos.ubSesiMeja?.[this.props.table.id];
    },
    get ubLabel() {
        const sesi = this.ubSesi;
        if (!sesi) {
            return "";
        }
        const status = sesi.status === "melewati_batas" ? _t("Lewat batas") : _t("Berjalan");
        return _t("%s · %s mnt", status, sesi.durasi_menit);
    },
    get style() {
        const warna = this.ubSesi && WARNA[this.ubSesi.status];
        if (!warna) {
            return super.style;
        }
        return `${super.style} background: ${warna.background}; border-color: ${warna.background}; color: ${warna.text};`;
    },
});
