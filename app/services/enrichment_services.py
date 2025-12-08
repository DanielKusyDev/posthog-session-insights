from sqlalchemy.ext.asyncio import AsyncConnection

from app.db_models import enriched_event
from app.models import EnrichedEvent, RawEvent, Session
from app.services.event_parsing import classify_event, extract_page_info, parse_elements_chain
from app.services.event_services import build_context
from app.services.semantic_builder_services import SemanticLabelBuilder

_label_builder = SemanticLabelBuilder()


async def create_enriched_event(connection: AsyncConnection, input_data: EnrichedEvent) -> None:
    stmt = enriched_event.insert().values(**input_data.model_dump())
    await connection.execute(stmt)


async def enrich_event(event: RawEvent, session: Session) -> EnrichedEvent:
    element_info = parse_elements_chain(chain=event.elements_chain)
    classification = classify_event(event_name=event.event_name, properties=event.properties)
    page_info = extract_page_info(properties=event.properties)
    semantic_label = _label_builder.build(
        event_type=classification.event_type,
        action_type=classification.action_type,
        page_info=page_info,
        element_info=element_info,
        event_name=event.event_name,
        properties=event.properties,
    )

    context = await build_context(event_name=event.event_name, properties=event.properties, element_info=element_info)
    sequence_number = session.event_count + 1

    return EnrichedEvent(
        raw_event_id=event.raw_event_id,
        user_id=event.user_id,
        session_id=session.session_id,
        timestamp=event.timestamp,
        event_name=event.event_name,
        event_type=classification.event_type,
        action_type=classification.action_type,
        semantic_label=semantic_label,
        page_path=page_info.page_path,
        page_title=page_info.page_title,
        element_type=element_info.element_type,
        element_text=element_info.element_text,
        context=context,
        sequence_number=sequence_number,
    )
