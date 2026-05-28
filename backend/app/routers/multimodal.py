from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status

from ..dependencies import RequestContext, get_multimodal_service, get_request_context
from ..multimodal_schemas import (
    AudioTranscriptionResponse,
    ImageProcessingResponse,
    RawClinicalTextResponse,
)
from ..services.multimodal import MediaProcessingError, MediaValidationError, MultimodalService


router = APIRouter(prefix="/multimodal/patients", tags=["Multi-modal Input Processing"])
PATIENT_PATH = Path(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")
DOCUMENT_FORM = Form(min_length=2, max_length=128, pattern=r"^[A-Za-z0-9._-]+$")


@router.post("/{patient_id}/audio:transcribe", response_model=AudioTranscriptionResponse)
async def transcribe_audio(
    patient_id: Annotated[str, PATIENT_PATH],
    audio: Annotated[UploadFile, File(description="Clinical conversation .mp3 or .wav")],
    document_id: Annotated[str, DOCUMENT_FORM],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MultimodalService, Depends(get_multimodal_service)],
    language: Annotated[str | None, Form(max_length=30)] = "vi",
) -> AudioTranscriptionResponse:
    try:
        content = await audio.read()
        return service.transcribe_audio(
            context.tenant_id,
            patient_id,
            document_id,
            audio.filename or "",
            audio.content_type or "",
            content,
            language,
        )
    except MediaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except MediaProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    finally:
        await audio.close()


@router.post("/{patient_id}/images:process", response_model=ImageProcessingResponse)
async def process_diagnostic_image(
    patient_id: Annotated[str, PATIENT_PATH],
    image: Annotated[UploadFile, File(description="Diagnostic image PNG/JPEG/TIFF")],
    document_id: Annotated[str, DOCUMENT_FORM],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MultimodalService, Depends(get_multimodal_service)],
    attached_clinical_text: Annotated[str | None, Form(max_length=1_000_000)] = None,
) -> ImageProcessingResponse:
    try:
        content = await image.read()
        return service.process_image(
            context.tenant_id,
            patient_id,
            document_id,
            image.filename or "",
            image.content_type or "",
            content,
            attached_clinical_text,
        )
    except MediaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except MediaProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    finally:
        await image.close()


@router.post("/{patient_id}/inputs:prepare", response_model=RawClinicalTextResponse)
async def prepare_multimodal_input(
    patient_id: Annotated[str, PATIENT_PATH],
    context: Annotated[RequestContext, Depends(get_request_context)],
    service: Annotated[MultimodalService, Depends(get_multimodal_service)],
    encounter_id: Annotated[str | None, Form(max_length=128)] = None,
    language: Annotated[str | None, Form(max_length=30)] = "vi",
    audio_document_id: Annotated[str | None, Form(max_length=128)] = None,
    image_document_id: Annotated[str | None, Form(max_length=128)] = None,
    attached_clinical_text: Annotated[str | None, Form(max_length=1_000_000)] = None,
    audio: Annotated[UploadFile | None, File(description="Optional .mp3 or .wav")] = None,
    image: Annotated[UploadFile | None, File(description="Optional diagnostic image")] = None,
) -> RawClinicalTextResponse:
    try:
        audio_result = None
        image_result = None
        if audio:
            if not audio_document_id:
                raise MediaValidationError("audio_document_id is required when audio is uploaded.")
            audio_result = service.transcribe_audio(
                context.tenant_id,
                patient_id,
                audio_document_id,
                audio.filename or "",
                audio.content_type or "",
                await audio.read(),
                language,
            )
        if image:
            if not image_document_id:
                raise MediaValidationError("image_document_id is required when image is uploaded.")
            image_result = service.process_image(
                context.tenant_id,
                patient_id,
                image_document_id,
                image.filename or "",
                image.content_type or "",
                await image.read(),
                attached_clinical_text,
            )
        return service.prepare_raw_clinical_text(
            context.tenant_id,
            patient_id,
            encounter_id,
            audio_result,
            image_result,
        )
    except MediaValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except MediaProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    finally:
        if audio:
            await audio.close()
        if image:
            await image.close()
