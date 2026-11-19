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

    async function run(work) {
        if (busy) return;
        busy = true;
        notice("");
        try {
            await work();
        } catch (error) {
            const detail = error.responseJSON?.detail;
            notice(typeof detail === "string" ? detail : "Не удалось выполнить запрос. Проверьте поля и попробуйте ещё раз.", true);
        } finally {
            busy = false;
        }
    }

    function options(select, excluded = []) {
        select.empty().append($("<option>").val("").text("Выберите оффер"));
        catalog.filter(offer => !excluded.includes(offer.id)).forEach(offer => {
            select.append($("<option>").val(offer.id).text(`#${offer.id} · ${offer.name}`));
        });
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
                .on("click", () => run(async () => {
                    if (!await deleteCampaign(entry)) return;
                    await refreshList();
                    notice("Кампания удалена");
                }));
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

    async function deleteCampaign(value) {
        if (!window.confirm(`Удалить кампанию «${value.name}»?`)) return false;
        await request(`/api/campaigns/${value.id}`, "DELETE");
        return true;
    }

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
            form.elements[field].value = value[field];
        }
        $("#routing").text(`${value.flows[0].country} → Google`);
        const offers = value.flows[1].offers;
        const rows = $("#offer-rows").empty();
        offers.forEach(offer => {
            const remove = $("<button>", {type: "button"}).addClass("btn btn-sm btn-outline-danger")
                .prop("disabled", offers.length === 1)
                .attr("aria-label", `Удалить оффер ${offer.name}`)
                .text("Удалить")
                .on("click", () => run(async () => {
                    show(await request(`/api/campaigns/${value.id}/offers/${offer.id}`, "DELETE"));
                    notice("Оффер удалён");
                }));
            rows.append($("<tr>").append(
                $("<td>").text(`#${offer.id} · ${offer.name}`),
                $("<td>").addClass("share").text(`${(offer.share_basis_points / 100).toLocaleString("ru", {maximumFractionDigits: 2})}%`),
                $("<td>").append(remove)
            ));
        });
        options($("#add-offer"), offers.map(offer => offer.id));
        $("#offer-form button").prop("disabled", offers.length >= catalog.length);
    }

    $(form).on("submit", event => {
        event.preventDefault();
        run(async () => {
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
        });
    });

    $("#delete").on("click", () => run(async () => {
        if (await deleteCampaign(campaign)) window.location.assign("/campaigns");
    }));

    $("#offer-form").on("submit", event => {
        event.preventDefault();
        run(async () => {
            show(await request(`/api/campaigns/${campaign.id}/offers`, "POST", {
                offer_id: Number($("#add-offer").val())
            }));
            notice("Оффер добавлен");
        });
    });

    run(async () => {
        const path = window.location.pathname;
        const offersPage = path === "/offers";
        const editorPage = path.startsWith("/campaigns/");
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
        const creating = path === "/campaigns/new";
        $("#page-title").text(creating ? "Новая кампания" : "Редактор кампании");
        $("#back").prop("hidden", false);
        catalog = await request("/api/offers");
        options($("#offer"));
        show(creating ? null : await request(`/api${path}`));
        $("#editor-page").prop("hidden", false);
    });
});
