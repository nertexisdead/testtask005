import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from fastapi import HTTPException


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class KeitaroCampaignService:
    def __init__(self):
        base = os.environ.get("KEITARO_URL", "").rstrip("/")
        key = os.environ.get("KEITARO_API_KEY", "")
        parsed = urlsplit(base)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.path
                or parsed.query or parsed.fragment or parsed.username is not None or not key):
            raise HTTPException(503, "Укажите HTTPS-адрес Keitaro без пути и API-ключ")
        self.base = base + "/admin_api/v1"
        self.headers = {"Api-Key": key, "Content-Type": "application/json",
                        "Accept": "application/json", "User-Agent": "Adrobot/1.0"}
        self.prefix = os.environ.get("KEITARO_CAMPAIGN_PREFIX") or "test_komarov_"
        self.enable_on_create = os.environ.get("KEITARO_ENABLE_ON_CREATE") == "true"
        self.opener = build_opener(NoRedirect())

    def _request(self, path, method="GET", data=None):
        body = json.dumps(data).encode() if data is not None else None
        request = Request(self.base + path, data=body, headers=self.headers, method=method)
        try:
            with self.opener.open(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except HTTPError as error:
            status = 404 if error.code == 404 else 502
            raise HTTPException(status, f"Keitaro вернул HTTP {error.code} для {method} {path}") from error
        except (URLError, TimeoutError, ValueError) as error:
            raise HTTPException(502, "Не удалось получить ответ от Keitaro") from error

    def settings(self):
        resources = {"domain": "/domains", "group": "/groups?type=campaigns", "source": "/traffic_sources"}
        return {
            field: [{"id": row["id"], "name": row["name"]} for row in self._request(path)
                    if row.get("state", "active") == "active"]
            for field, path in resources.items()
        }

    def catalog(self):
        return [{"id": row["id"], "name": row["name"]} for row in self._request("/offers")
                if row.get("state") == "active"]

    def list(self):
        settings = self.settings()
        results = []
        for row in self._request("/campaigns"):
            if row["name"].startswith(self.prefix):
                summary = self._summary(row, settings)
                streams = self._request(f"/campaigns/{row['id']}/streams")
                summary["geo"] = next(
                    (country for stream in streams for rule in stream.get("filters", [])
                     if rule.get("name") == "country" for country in rule.get("payload", [])),
                    "—",
                )
                results.append(summary)
        return results

    @staticmethod
    def _summary(row, settings):
        fields = {"domain": "domain_id", "group": "group_id", "source": "traffic_source_id"}
        return {
            "id": row["id"], "name": row["name"], "geo": "—",
            "state": row.get("state"),
            **{field: next((item["name"] for item in settings[field]
                            if str(item["id"]) == str(row.get(key))), "—")
               for field, key in fields.items()},
            "settings_ids": {field: row.get(key) for field, key in fields.items()},
        }

    def _payload(self, data):
        settings = self.settings()
        values = {}
        for field in ("domain", "group", "source"):
            value = getattr(data, field)
            item = next((row for row in settings[field] if str(row["id"]) == value), None)
            if item is None:
                raise HTTPException(422, f"Выберите значение Keitaro для поля {field}")
            values[field] = item["id"]
        name = data.name if data.name.startswith(self.prefix) else self.prefix + data.name
        return {"name": name, "domain_id": values["domain"], "group_id": values["group"],
                "traffic_source_id": values["source"]}

    def _offer(self, offer_id):
        row = self._request(f"/offers/{offer_id}")
        if row.get("state") != "active":
            raise HTTPException(422, "Выберите активный оффер")
        return row

    def _campaign(self, campaign_id):
        row = self._request(f"/campaigns/{campaign_id}")
        if not row["name"].startswith(self.prefix):
            raise HTTPException(404, "Кампания не найдена")
        return row

    def _flows(self, campaign_id):
        streams = self._request(f"/campaigns/{campaign_id}/streams")
        geo = [
            row for row in streams if row.get("schema") == "redirect"
            and any(rule.get("name") == "country" for rule in row.get("filters", []))
        ]
        offers = [row for row in streams if row.get("schema") == "landings"]
        if len(geo) != 1 or len(offers) != 1:
            raise HTTPException(409, "Нужен один геопоток и один поток офферов")
        countries = [rule for rule in geo[0]["filters"] if rule["name"] == "country"]
        if len(countries) != 1 or countries[0].get("mode") != "accept" or len(countries[0].get("payload") or []) != 1:
            raise HTTPException(409, "Редактор поддерживает геопоток с одной разрешённой страной")
        return geo[0], offers[0]

    def create(self, data):
        payload = self._payload(data)
        self._offer(data.offer_id)
        row = self._request("/campaigns", "POST", {
            **payload, "alias": uuid4().hex[:12], "type": "position", "state": "disabled",
        })
        campaign_id = row["id"]
        try:
            self._request("/streams", "POST", {
                "campaign_id": campaign_id, "name": "Geo", "position": 1,
                "type": "regular", "state": "active", "schema": "redirect", "action_type": "http",
                "action_options": {"url": "https://google.com/"},
                "filters": [self._country(data.geo)],
            })
            self._request("/streams", "POST", {
                "campaign_id": campaign_id, "name": "Offers", "position": 2,
                "type": "default", "state": "active", "schema": "landings", "action_type": "http",
                "landings": [], "offers": [{"offer_id": data.offer_id, "share": 100, "state": "active"}],
            })
        except HTTPException as error:
            raise HTTPException(error.status_code, f"Кампания #{campaign_id} оставлена выключенной. {error.detail}") from error
        try:
            view = self.get(campaign_id)
            if self.enable_on_create:
                self._request(f"/campaigns/{campaign_id}/enable", "POST")
                return self.get(campaign_id)
            return view
        except HTTPException as error:
            raise HTTPException(
                error.status_code, f"Кампания #{campaign_id} создана. Проверьте её состояние. {error.detail}",
            ) from error

    @staticmethod
    def _country(geo):
        return {"name": "country", "mode": "accept", "payload": [geo.upper()]}

    def get(self, campaign_id):
        summary = self._summary(self._campaign(campaign_id), self.settings())
        geo, flow = self._flows(campaign_id)
        country = next(rule for rule in geo["filters"] if rule["name"] == "country")
        summary["geo"] = country["payload"][0]
        catalog = {row["id"]: row["name"] for row in self.catalog()}
        summary["flows"] = [
            {"position": geo["position"], "country": summary["geo"],
             "url": (geo.get("action_options") or {}).get("url") or geo.get("action_payload")},
            {"position": flow["position"], "offers": [
                {"id": row["offer_id"], "name": catalog.get(row["offer_id"], str(row["offer_id"])),
                 "state": row["state"], "share_basis_points": round(row["share"] * 100)}
                for row in flow["offers"]
            ]},
        ]
        return summary

    def update(self, campaign_id, data):
        row = self._campaign(campaign_id)
        geo, _ = self._flows(campaign_id)
        payload = self._payload(data)
        filters = [self._country(data.geo) if rule["name"] == "country" else rule for rule in geo["filters"]]
        self._request(f"/campaigns/{campaign_id}", "PUT", {**payload, "alias": row["alias"]})
        try:
            self._request(f"/streams/{geo['id']}", "PUT", {"filters": filters})
        except HTTPException as error:
            raise HTTPException(
                error.status_code, f"Параметры кампании сохранены. Обновление геопотока не подтверждено. {error.detail}",
            ) from error
        return self.get(campaign_id)

    def delete(self, campaign_id):
        self._campaign(campaign_id)
        self._request(f"/campaigns/{campaign_id}", "DELETE")

    def add_offer(self, campaign_id, offer_id):
        return self._change_offer(campaign_id, offer_id, adding=True)

    def remove_offer(self, campaign_id, offer_id):
        return self._change_offer(campaign_id, offer_id, adding=False)

    def _change_offer(self, campaign_id, offer_id, *, adding):
        self._campaign(campaign_id)
        _, flow = self._flows(campaign_id)
        rows = {row["offer_id"]: row for row in flow["offers"]}
        if adding == (offer_id in rows):
            return self.get(campaign_id)
        if adding:
            self._offer(offer_id)
            rows[offer_id] = {"offer_id": offer_id, "state": "active"}
        else:
            del rows[offer_id]
        active = [row["offer_id"] for row in rows.values() if row["state"] == "active"]
        if not 1 <= len(active) <= 100:
            raise HTTPException(409, "В потоке должно быть от 1 до 100 активных офферов")
        share, remainder = divmod(100, len(active))
        weights = {item: share + (index < remainder) for index, item in enumerate(active)}
        payload = [{"offer_id": item, "state": row["state"], "share": weights.get(item, row.get("share", 0))}
                   for item, row in rows.items()]
        self._request(f"/streams/{flow['id']}", "PUT", {"offers": payload})
        return self.get(campaign_id)
