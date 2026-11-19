jQuery(function ($) {
    const form = $("#campaign-form")[0];
    let campaign = null;
    let catalog = [];
    let busy = false;

    function request(url, method = "GET", body) {
        return $.ajax({
            url, method,
            contentType: "application/json",
            data: body === undefined ? undefined : JSON.stringify(body)
        });
    }

    function notice(message, error = false) {
        $("#notice").text(message).toggleClass("error", error).prop("hidden", !message);
    }

    async function run(message, work, button, status = $("#request-status")) {
        if (busy) return;
        busy = true;
        notice("");
        $("#campaign-page, #offers-page, #editor-page").attr("aria-busy", "true");
        status.append(
            $("<span>", {class: "spinner-border spinner-border-sm", "aria-hidden": "true"}),
            $("<span>").text(message)
        );
        button?.setAttribute("aria-disabled", "true");
        try {
            await work();
        } catch (error) {
            const detail = error.responseJSON?.detail;
            notice(typeof detail === "string" ? detail : "Не удалось выполнить запрос. Проверьте поля и попробуйте ещё раз.", true);
        } finally {
            button?.removeAttribute("aria-disabled");
            $("#campaign-page, #offers-page, #editor-page").attr("aria-busy", "false");
            status.empty();
            busy = false;
        }
    }

    function options(select, excluded = []) {
        select.empty().append($("<option>").val("").text("Выберите оффер"));
        catalog.filter(offer => !excluded.includes(offer.id)).forEach(offer => {
            select.append($("<option>").val(offer.id).text(`#${offer.id} · ${offer.name}`));
        });
        return select[0].options.length > 1;
    }

    async function refreshList() {
        const entries = await request("/api/campaigns");
        const list = $("#campaign-list").empty();
        $("#count").text(`Всего кампаний: ${entries.length}`);
        if (!entries.length) {
            list.append($("<tr>").append($("<td>", {colspan: 6}).addClass("empty").text("Кампаний пока нет")));
        }
        entries.forEach(entry => {
            const edit = $("<a>", {href: `/campaigns/${entry.id}`, class: "btn btn-sm btn-outline-light"})
                .text("Редактировать");
            const remove = $("<button>", {type: "button", class: "btn btn-sm btn-outline-danger"})
                .text("Удалить")
                .on("click", event => {
                    if (busy || !confirmDelete(entry)) return;
                    run("Удаляем кампанию…", async () => {
                        await deleteCampaign(entry);
                        await refreshList();
                        notice("Кампания удалена");
                    }, event.currentTarget);
                });
            list.append($("<tr>").append(
                $("<th>", {scope: "row"}).text(entry.name),
                $("<td>", {"data-label": "Домен"}).text(entry.domain),
                $("<td>", {"data-label": "Гео"}).text(entry.geo),
                $("<td>", {"data-label": "Группа"}).text(entry.group),
                $("<td>", {"data-label": "Источник"}).text(entry.source),
                $("<td>", {class: "actions-cell"}).append($("<div>", {class: "row-actions"}).append(edit, remove))
            ));
        });
    }

    const confirmDelete = value => window.confirm(`Удалить кампанию «${value.name}»?`);
    const deleteCampaign = value => request(`/api/campaigns/${value.id}`, "DELETE");

    function show(value) {
        campaign = value;
        form.reset();
        $("#editor-title").text(value?.name ?? "Новая кампания");
        $("#initial-offer, #flows, #delete").each(function () {
            this.hidden = this.id === "initial-offer" ? !!value : !value;
        });
        $("#offer").prop("disabled", !!value);
        $("#save").text(value ? "Сохранить" : "Создать кампанию");
        if (!value) return;
        for (const field of ["name", "geo", "domain", "group", "source"]) {
            form.elements[field].value = value.settings_ids?.[field] ?? value[field];
        }
        const geoFlow = value.flows[0];
        $("#routing").text(geoFlow.url ? `${geoFlow.country} → ${geoFlow.url}` : geoFlow.country);
        $("#campaign-state").text(value.state === "active" ? "Кампания активна в Keitaro" : "Кампания выключена в Keitaro")
            .prop("hidden", !value.state);
        const offers = value.flows[1].offers;
        const stateIsActive = offer => !offer.state || offer.state === "active";
        const activeCount = offers.filter(stateIsActive).length;
        const rows = $("#offer-rows").empty();
        offers.forEach(offer => {
            const remove = $("<button>", {type: "button"}).addClass("btn btn-sm btn-outline-danger")
                .prop("disabled", stateIsActive(offer) && activeCount === 1)
                .attr("aria-label", `Удалить оффер ${offer.name}`)
                .text("Удалить")
                .on("click", event => run("Удаляем оффер…", async () => {
                    show(await request(`/api/campaigns/${value.id}/offers/${offer.id}`, "DELETE"));
                    notice("Оффер удалён");
                }, event.currentTarget));
            rows.append($("<tr>").append(
                $("<td>").text(`#${offer.id} · ${offer.name}${stateIsActive(offer) ? "" : " · выключен"}`),
                $("<td>").addClass("share").text(stateIsActive(offer)
                    ? `${(offer.share_basis_points / 100).toLocaleString("ru", {maximumFractionDigits: 2})}%` : "—"),
                $("<td>").append(remove)
            ));
        });
        const hasAvailableOffers = options($("#add-offer"), offers.map(offer => offer.id));
        $("#offer-form button").prop("disabled", !hasAvailableOffers);
    }

    $(form).on("submit", event => {
        event.preventDefault();
        run(campaign ? "Сохраняем кампанию…" : "Создаём кампанию…", async () => {
            const body = Object.fromEntries(new FormData(form));
            if (!campaign) body.offer_id = Number(body.offer_id);
            const editing = !!campaign;
            const saved = await request(editing ? `/api/campaigns/${campaign.id}` : "/api/campaigns", editing ? "PUT" : "POST", body);
            if (!editing) {
                window.location.assign(`/campaigns/${saved.id}`);
                return;
            }
            show(saved);
            notice("Кампания сохранена");
        }, $("#save")[0]);
    });

    $("#delete").on("click", event => {
        if (busy || !confirmDelete(campaign)) return;
        run("Удаляем кампанию…", async () => {
            await deleteCampaign(campaign);
            window.location.assign("/campaigns");
        }, event.currentTarget);
    });

    $("#offer-form").on("submit", event => {
        event.preventDefault();
        run("Добавляем оффер…", async () => {
            show(await request(`/api/campaigns/${campaign.id}/offers`, "POST", {
                offer_id: Number($("#add-offer").val())
            }));
            notice("Оффер добавлен");
        }, $("#offer-form button")[0]);
    });

    const path = window.location.pathname;
    const editorPage = path.startsWith("/campaigns/");
    const creating = path === "/campaigns/new";
    const loadingMessage = editorPage
        ? (creating ? "Загружаем справочники и офферы…" : "Загружаем кампанию и офферы…")
        : "Загружаем данные…";

    run(loadingMessage, async () => {
        const offersPage = path === "/offers";
        $("#nav-offers").toggleClass("active", offersPage);
        $("#nav-campaigns").toggleClass("active", !offersPage);
        if (!offersPage && !editorPage) {
            $("#campaign-page, #new").prop("hidden", false);
            await refreshList();
            return;
        }
        if (offersPage) {
            $("#page-title").text("Офферы");
            $("#offers-page").prop("hidden", false);
            const offers = await request("/api/offers");
            offers.forEach(offer => {
                $("#catalog-rows").append($("<tr>").append(
                    $("<td>").text(`#${offer.id}`),
                    $("<td>").text(offer.name)
                ));
            });
            return;
        }
        $("#page-title").text(creating ? "Новая кампания" : "Редактор кампании");
        $("#back").prop("hidden", false);
        const [offers, remoteSettings, currentCampaign] = await Promise.all([
            request("/api/offers"),
            request("/api/settings"),
            creating ? null : request(`/api${path}`)
        ]);
        catalog = offers;
        if (remoteSettings) {
            for (const field of ["domain", "group", "source"]) {
                const select = $("<select>", {class: "form-control", name: field, required: true});
                optionsForSettings(select, remoteSettings[field]);
                $(form.elements[field]).replaceWith(select);
            }
        }
        options($("#offer"));
        show(currentCampaign);
        $("#editor-page").prop("hidden", false);
    }, undefined, editorPage ? $("#editor-loading") : $("#request-status"));

    function optionsForSettings(select, entries) {
        entries.forEach(entry => select.append($("<option>").val(entry.id).text(entry.name)));
    }
});
