import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, Session as DatabaseSession, mapped_column, relationship

from database import Base, Session
from keitaro import KeitaroCampaignService


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str]


class CampaignOffer(Base):
    __tablename__ = "campaign_offers"

    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id"), primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), primary_key=True)
    offer: Mapped[Offer] = relationship()


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    geo: Mapped[str]
    domain: Mapped[str]
    group: Mapped[str]
    source: Mapped[str]
    offers: Mapped[list[CampaignOffer]] = relationship(
        order_by=CampaignOffer.offer_id, cascade="all, delete-orphan",
    )


PositiveId = Annotated[int, Field(gt=0, le=2147483647)]


class OfferInput(BaseModel):
    offer_id: PositiveId


class CampaignFields(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    geo: Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[A-Za-z]{2}$")]
    domain: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    group: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    source: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class CampaignInput(CampaignFields, OfferInput):
    pass


class CampaignService:
    def __init__(self, session: DatabaseSession):
        self.session = session

    def list(self):
        rows = self.session.scalars(select(Campaign).order_by(Campaign.id.desc()))
        return [
            {"id": row.id, "name": row.name, "domain": row.domain, "geo": row.geo,
             "group": row.group, "source": row.source}
            for row in rows
        ]

    def catalog(self):
        rows = self.session.scalars(select(Offer).order_by(Offer.id))
        return [{"id": row.id, "name": row.name} for row in rows]

    def create(self, data: CampaignInput):
        campaign = Campaign(**data.model_dump(exclude={"offer_id"}))
        campaign.geo = campaign.geo.upper()
        campaign.offers.append(CampaignOffer(offer=self._offer(data.offer_id)))
        self.session.add(campaign)
        return self._save(campaign)

    def get(self, campaign_id: int):
        return self._view(self._campaign(campaign_id))

    def update(self, campaign_id: int, data: CampaignFields):
        campaign = self._campaign(campaign_id, lock=True)
        for field, value in data.model_dump().items():
            setattr(campaign, field, value)
        campaign.geo = campaign.geo.upper()
        return self._save(campaign)

    def delete(self, campaign_id: int):
        self.session.delete(self._campaign(campaign_id, lock=True))
        self.session.commit()

    def add_offer(self, campaign_id: int, offer_id: int):
        campaign = self._campaign(campaign_id, lock=True)
        if all(link.offer_id != offer_id for link in campaign.offers):
            if len(campaign.offers) == 100:
                raise HTTPException(409, "Поток поддерживает до 100 офферов")
            campaign.offers.append(CampaignOffer(offer=self._offer(offer_id)))
        return self._save(campaign)

    def remove_offer(self, campaign_id: int, offer_id: int):
        campaign = self._campaign(campaign_id, lock=True)
        for link in campaign.offers:
            if link.offer_id == offer_id:
                if len(campaign.offers) == 1:
                    raise HTTPException(409, "В потоке должен остаться хотя бы один оффер")
                campaign.offers.remove(link)
                break
        return self._save(campaign)

    def _campaign(self, campaign_id: int, *, lock=False):
        campaign = self.session.get(Campaign, campaign_id, with_for_update=lock)
        if campaign is None:
            raise HTTPException(404, "Кампания не найдена")
        return campaign

    def _offer(self, offer_id: int):
        offer = self.session.get(Offer, offer_id)
        if offer is None:
            raise HTTPException(404, "Оффер не найден в локальном каталоге")
        return offer

    def _save(self, campaign: Campaign):
        self.session.flush()
        view = self._view(campaign)
        self.session.commit()
        return view

    @staticmethod
    def _view(campaign: Campaign):
        links = sorted(campaign.offers, key=lambda link: link.offer_id)
        share, remainder = divmod(10000, len(links))
        return {
            "id": campaign.id,
            "name": campaign.name,
            "geo": campaign.geo,
            "domain": campaign.domain,
            "group": campaign.group,
            "source": campaign.source,
            "flows": [
                {"position": 1, "country": campaign.geo, "url": "https://google.com/"},
                {"position": 2, "offers": [
                    {"id": link.offer_id, "name": link.offer.name,
                     "share_basis_points": share + (index < remainder)}
                    for index, link in enumerate(links)
                ]},
            ],
        }


def campaign_service():
    if os.environ.get("KEITARO_URL") or os.environ.get("KEITARO_API_KEY"):
        yield KeitaroCampaignService()
        return
    with Session() as session:
        yield CampaignService(session)


Service = Annotated[CampaignService | KeitaroCampaignService, Depends(campaign_service)]
router = APIRouter(prefix="/api")


@router.get("/settings")
def campaign_settings(service: Service):
    return service.settings() if isinstance(service, KeitaroCampaignService) else None


@router.get("/offers")
def list_offers(service: Service):
    return service.catalog()


@router.get("/campaigns")
def list_campaigns(service: Service):
    return service.list()


@router.post("/campaigns", status_code=201)
def create_campaign(data: CampaignInput, service: Service):
    return service.create(data)


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: PositiveId, service: Service):
    return service.get(campaign_id)


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: PositiveId, data: CampaignFields, service: Service):
    return service.update(campaign_id, data)


@router.delete("/campaigns/{campaign_id}", status_code=204)
def delete_campaign(campaign_id: PositiveId, service: Service):
    service.delete(campaign_id)


@router.post("/campaigns/{campaign_id}/offers")
def add_offer(campaign_id: PositiveId, data: OfferInput, service: Service):
    return service.add_offer(campaign_id, data.offer_id)


@router.delete("/campaigns/{campaign_id}/offers/{offer_id}")
def remove_offer(campaign_id: PositiveId, offer_id: PositiveId, service: Service):
    return service.remove_offer(campaign_id, offer_id)
