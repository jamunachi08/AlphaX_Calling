// Browser softphone (Twilio Voice SDK, bundled). Loaded only when the site has browser calling configured.
(function () {
    const ax = window.alphax_calling, SDK = "/assets/alphax_calling/js/vendor/twilio-voice-sdk-2.19.0.min.js";
    const sp = ax.softphone = {device: null, call: null, timer: null, panel: null};

    sp.available = () => !!(frappe.boot && frappe.boot.alphax_browser_calling);

    sp.ensure = async function () {
        if (this.device) return this.device;
        await frappe.require(SDK);
        const fetchToken = async () => (await frappe.xcall("alphax_calling.twilio_adapter.get_token")).token;
        const device = new Twilio.Device(await fetchToken(), {codecPreferences: ["opus", "pcmu"], closeProtection: true});
        device.on("tokenWillExpire", async () => device.updateToken(await fetchToken()));
        device.on("error", e => frappe.show_alert({message: ax.esc(e.message || e), indicator: "red"}, 8));
        device.on("incoming", call => this.incoming(call));
        await device.register();
        return (this.device = device);
    };

    sp.ui = function (html) {
        if (!this.panel) {
            this.panel = $('<div class="alphax-softphone" style="position:fixed;right:16px;bottom:16px;z-index:1050;' +
                'min-width:260px;padding:12px 14px;border-radius:10px;background:var(--card-bg);color:var(--text-color);' +
                'border:1px solid var(--border-color);box-shadow:var(--shadow-lg)"></div>').appendTo(document.body);
        }
        this.panel.html(html).show();
        return this.panel;
    };
    sp.close = function () {
        clearInterval(this.timer);
        this.call = null;
        if (this.panel) this.panel.hide();
    };

    sp.inCall = function (call, label) {
        this.call = call;
        const started = Date.now();
        const p = this.ui(`<div><b>${ax.esc(label)}</b></div><div class="ax-status text-muted">${__("Connecting…")}</div>
            <div class="mt-2"><button class="btn btn-xs btn-default ax-mute">${__("Mute")}</button>
            <button class="btn btn-xs btn-danger ax-hang">${__("Hang up")}</button></div>`);
        p.find(".ax-hang").on("click", () => call.disconnect());
        p.find(".ax-mute").on("click", e => { call.mute(!call.isMuted()); $(e.target).text(call.isMuted() ? __("Unmute") : __("Mute")); });
        call.on("accept", () => {
            clearInterval(this.timer);
            this.timer = setInterval(() => {
                const s = Math.floor((Date.now() - started) / 1000);
                p.find(".ax-status").text(String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0"));
            }, 1000);
        });
    };

    sp.incoming = function (call) {
        if (this.call) return call.reject();
        const cp = call.customParameters, lead = cp && cp.get("lead"), name = cp && cp.get("lead_name");
        const who = name || call.parameters.From || __("Unknown caller");
        const p = this.ui(`<div><b>${__("Incoming call")}</b></div><div>${ax.esc(who)}</div>
            <div class="mt-2"><button class="btn btn-xs btn-success ax-acc">${__("Accept")}</button>
            <button class="btn btn-xs btn-default ax-dec">${__("Decline")}</button>
            ${lead ? `<a class="btn btn-xs btn-link" href="${frappe.utils.get_form_link("Lead", lead)}">${__("Open Lead")}</a>` : ""}</div>`);
        call.on("cancel", () => this.close());
        call.on("disconnect", () => this.close());
        p.find(".ax-dec").on("click", () => { call.reject(); this.close(); });
        p.find(".ax-acc").on("click", () => { call.accept(); this.inCall(call, who); call.on("disconnect", () => this.close()); });
    };

    // Resolves when the call ends (for any reason).
    sp.dial = async function (number, attempt, label) {
        if (this.call) frappe.throw(__("You are already on a call."));
        const device = await this.ensure();
        const call = await device.connect({params: {To: number, AttemptId: attempt}});
        this.inCall(call, label || number);
        return new Promise(resolve => {
            let done = false;
            const end = () => { if (!done) { done = true; this.close(); resolve(); } };
            call.on("disconnect", end); call.on("cancel", end); call.on("reject", end);
            call.on("error", e => { frappe.msgprint(ax.esc(e.message || e)); end(); });
        });
    };

    // Register at start so inbound calls can ring in the browser.
    $(document).on("startup", () => { if (sp.available()) sp.ensure().catch(() => {}); });
})();
