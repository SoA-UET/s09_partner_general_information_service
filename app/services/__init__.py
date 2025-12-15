from .ConversationService import ConversationService
from .PartnerInformationService import PartnerInformationService
from ..collections import conversations_collection, partner_information_collection

conversation_service = ConversationService(
    collection=conversations_collection,
)

partner_information_service = PartnerInformationService(
    collection=partner_information_collection,
)
