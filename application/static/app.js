jQuery(function ($) {
    const button = $("#check");
    const status = $("#status");

    function checkHealth() {
        button.prop("disabled", true);
        status.text("Проверяем подключение…");

        $.getJSON("/api/health")
            .done(() => status.text("FastAPI и PostgreSQL доступны."))
            .fail(() => status.text("Не удалось получить статус API и базы."))
            .always(() => button.prop("disabled", false));
    }

    button.on("click", checkHealth);
    checkHealth();
});
