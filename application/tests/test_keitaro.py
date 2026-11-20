from io import BytesIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from fastapi import HTTPException

from keitaro import KeitaroCampaignService


class KeitaroCampaignTests(TestCase):
    def setUp(self):
        environment = {
            "KEITARO_URL": "https://tracker.example.org",
            "KEITARO_API_KEY": "test-key",
            "KEITARO_CAMPAIGN_PREFIX": "test_komarov_",
            "KEITARO_ENABLE_ON_CREATE": "false",
        }
        with patch.dict("os.environ", environment):
            self.service = KeitaroCampaignService()

    def test_validation_error_exposes_field_without_upstream_content(self):
        body = BytesIO(b'{"name":["upstream sensitive detail"]}')
        error = HTTPError(self.service.base, 422, "Invalid", None, body)
        self.service.opener.open = Mock(side_effect=error)

        with self.assertRaises(HTTPException) as failure:
            self.service._request("/campaigns", "POST", {})

        self.assertEqual(failure.exception.status_code, 422)
        self.assertIn("название кампании", failure.exception.detail)
        self.assertNotIn("upstream sensitive detail", failure.exception.detail)

    def test_prefix_counts_toward_name_limit(self):
        with self.assertRaises(HTTPException) as failure:
            self.service._payload(SimpleNamespace(name="x" * 120))

        self.assertEqual(failure.exception.status_code, 422)

    def test_partial_creation_reports_existing_disabled_campaign(self):
        self.service.settings = Mock(return_value={
            "domain": [{"id": 1}], "group": [{"id": 2}], "source": [{"id": 3}],
        })
        self.service._offer = Mock()
        self.service._request = Mock(side_effect=[
            {"id": 42}, {}, HTTPException(502, "Failed to create stream"),
        ])
        data = SimpleNamespace(name="demo", geo="au", domain="1", group="2", source="3", offer_id=7)

        with self.assertRaises(HTTPException) as failure:
            self.service.create(data)

        self.assertIn("#42", failure.exception.detail)
        campaign, geo, offers = [call.args[2] for call in self.service._request.call_args_list]
        self.assertEqual(campaign["state"], "disabled")
        self.assertEqual(geo["filters"], [{"name": "country", "mode": "accept", "payload": ["AU"]}])
        self.assertEqual(offers["offers"], [{"offer_id": 7, "share": 100, "state": "active"}])

    def test_offer_weights_and_repeat_requests(self):
        flow = {"id": 9, "offers": [{"offer_id": 7, "state": "active", "share": 100}]}
        self.service._campaign = Mock()
        self.service._flows = Mock(return_value=({}, flow))
        self.service._offer = Mock()
        self.service.get = Mock()

        def replace_offers(path, method, data):
            self.assertEqual((path, method), ("/streams/9", "PUT"))
            flow["offers"] = data["offers"]

        self.service._request = Mock(side_effect=replace_offers)
        self.service.add_offer(42, 8)
        self.assertEqual([row["share"] for row in flow["offers"]], [50, 50])
        self.service.add_offer(42, 8)
        self.assertEqual(self.service._request.call_count, 1)
        self.service.remove_offer(42, 8)
        self.assertEqual(flow["offers"], [{"offer_id": 7, "state": "active", "share": 100}])
        with self.assertRaises(HTTPException) as failure:
            self.service.remove_offer(42, 7)
        self.assertEqual(failure.exception.status_code, 409)
        self.assertEqual(self.service._request.call_count, 2)
