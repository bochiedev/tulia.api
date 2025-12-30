"""
Celery tasks for LangGraph orchestration.

Handles asynchronous processing of inbound messages using the LangGraph orchestrator.
Legacy AI agent service and direct LLM calls have been removed.
"""
import asyncio
import logging
from celery import shared_task
from django.utils import timezone
from django.db import models

from apps.bot.conversation_state import ConversationState, ConversationStateManager

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_inbound_message(self, message_id: str):
    """
    Process inbound message using LangGraph orchestrator.
    
    All messages are processed through the LangGraph state machine.
    Legacy AI agent service and direct LLM calls have been removed.
    
    Args:
        message_id: UUID of the Message to process
        
    Flow:
        1. Load message and conversation
        2. Process through LangGraph orchestrator
        3. Send response via Twilio
        4. Update conversation state
    """
    from apps.messaging.models import Message, Conversation
    from apps.bot.langgraph.orchestrator import LangGraphOrchestrator
    from apps.integrations.services.twilio_service import create_twilio_service_for_tenant
    from apps.bot.conversation_state import ConversationStateManager
    from apps.bot.models import ConversationSession
    from django.db import transaction
    
    try:
        # Load message
        message = Message.objects.select_related(
            'conversation',
            'conversation__tenant',
            'conversation__customer'
        ).get(id=message_id)
        
        conversation = message.conversation
        tenant = conversation.tenant
        customer = conversation.customer
        
        logger.info(
            f"Processing inbound message via LangGraph",
            extra={
                'message_id': str(message_id),
                'conversation_id': str(conversation.id),
                'tenant_id': str(tenant.id)
            }
        )
        
        # Check if conversation is in handoff mode
        if conversation.status == 'handoff':
            logger.info(
                f"Skipping bot processing - conversation in handoff mode",
                extra={
                    'message_id': str(message_id),
                    'conversation_id': str(conversation.id)
                }
            )
            return {
                'status': 'skipped',
                'reason': 'handoff_active',
                'message_id': str(message_id)
            }
        
        # Get or create conversation session for state management
        session, created = ConversationSession.objects.get_or_create(
            tenant=tenant,
            conversation=conversation,
            defaults={
                'customer': customer,
                'is_active': True,
                'state_data': ConversationStateManager.serialize_for_storage(
                    ConversationState(
                        tenant_id=str(tenant.id),
                        conversation_id=str(conversation.id),
                        request_id=str(message.id),
                        customer_id=str(customer.id) if customer else None,
                        phone_e164=customer.phone_e164 if customer else None
                    )
                ),
                'last_request_id': str(message.id)
            }
        )
        
        # Deserialize existing state or create initial state
        if session.state_data and session.state_data != '{}':
            existing_state = ConversationStateManager.deserialize_from_storage(session.state_data)
        else:
            existing_state = None
        
        # Initialize LangGraph orchestrator
        orchestrator = LangGraphOrchestrator()
        
        # Process message through LangGraph
        updated_state = asyncio.run(orchestrator.process_message(
            tenant_id=str(tenant.id),
            conversation_id=str(conversation.id),
            request_id=str(message.id),  # Use message ID as request ID
            message_text=message.text,
            phone_e164=customer.phone_e164 if customer else None,
            customer_id=str(customer.id) if customer else None,
            existing_state=existing_state
        ))
        
        # Send response if generated
        if updated_state.response_text:
            twilio_service = create_twilio_service_for_tenant(tenant)
            
            # Send the response
            twilio_service.send_whatsapp(
                to=customer.phone_e164,
                body=updated_state.response_text
            )
            
            logger.info(
                f"Response sent via Twilio",
                extra={
                    'message_id': str(message_id),
                    'conversation_id': str(conversation.id),
                    'response_length': len(updated_state.response_text)
                }
            )
        
        # Update conversation session with new state
        session.state_data = ConversationStateManager.serialize_for_storage(updated_state)
        session.updated_at = timezone.now()
        session.save()
        
        # Handle escalation if required
        if updated_state.escalation_required:
            conversation.handoff_active = True
            conversation.handoff_reason = updated_state.escalation_reason
            conversation.save()
            
            logger.info(
                f"Conversation escalated to human",
                extra={
                    'message_id': str(message_id),
                    'conversation_id': str(conversation.id),
                    'escalation_reason': updated_state.escalation_reason
                }
            )
        
        return {
            'status': 'success',
            'system': 'langgraph_orchestrator',
            'journey': updated_state.journey,
            'intent': updated_state.intent,
            'escalated': updated_state.escalation_required,
            'message_id': str(message_id)
        }
        
    except Exception as e:
        logger.error(
            f"Error processing message {message_id}: {e}",
            exc_info=True
        )
        
        # Return error response
        return {
            'status': 'error',
            'system': 'langgraph_orchestrator',
            'error': str(e),
            'message_id': str(message_id)
        }


@shared_task(bind=True, max_retries=2)
def process_document(self, document_id: str):
    """
    Process uploaded document: extract text, chunk, embed, and index.
    
    This task handles document processing for the knowledge base.
    It extracts text, chunks it, generates embeddings, and indexes
    the content for RAG retrieval.
    
    Args:
        document_id: UUID of the TenantDocument to process
    """
    from apps.bot.models_tenant_documents import TenantDocument
    from apps.bot.services.text_extraction_service import TextExtractionService
    from apps.bot.services.chunking_service import ChunkingService
    from apps.bot.services.embedding_service import EmbeddingService
    from apps.bot.services.document_store_service import DocumentStoreService
    
    try:
        # Load document
        document = TenantDocument.objects.select_related('tenant').get(id=document_id)
        
        logger.info(
            f"Processing document {document.title}",
            extra={
                'document_id': str(document_id),
                'tenant_id': str(document.tenant.id),
                'document_type': document.document_type
            }
        )
        
        # Extract text from document
        extraction_service = TextExtractionService()
        extracted_text = extraction_service.extract_text(
            file_path=document.file_path,
            document_type=document.document_type
        )
        
        # Update document with extracted text
        document.content = extracted_text
        document.processing_status = 'text_extracted'
        document.save()
        
        # Chunk the text
        chunking_service = ChunkingService()
        chunks = chunking_service.chunk_text(
            text=extracted_text,
            chunk_size=1000,
            overlap=200
        )
        
        # Generate embeddings for chunks
        embedding_service = EmbeddingService.create_for_tenant(document.tenant)
        
        # Store chunks in vector database
        document_store = DocumentStoreService()
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = embedding_service.generate_embedding(chunk)
            
            if embedding:
                # Store in vector database with tenant namespace
                document_store.store_chunk(
                    tenant_id=str(document.tenant.id),
                    document_id=str(document.id),
                    chunk_index=i,
                    content=chunk,
                    embedding=embedding,
                    metadata={
                        'document_title': document.title,
                        'document_type': document.document_type,
                        'chunk_index': i,
                        'total_chunks': len(chunks)
                    }
                )
        
        # Update document status
        document.processing_status = 'completed'
        document.processed_at = timezone.now()
        document.save()
        
        logger.info(
            f"Document processing completed: {len(chunks)} chunks indexed",
            extra={
                'document_id': str(document_id),
                'tenant_id': str(document.tenant.id),
                'chunks_count': len(chunks)
            }
        )
        
        return {
            'status': 'success',
            'document_id': str(document_id),
            'chunks_processed': len(chunks)
        }
        
    except Exception as e:
        logger.error(
            f"Error processing document {document_id}: {e}",
            exc_info=True
        )
        
        # Update document status to failed
        try:
            document = TenantDocument.objects.get(id=document_id)
            document.processing_status = 'failed'
            document.error_message = str(e)
            document.save()
        except:
            pass
        
        return {
            'status': 'error',
            'document_id': str(document_id),
            'error': str(e)
        }