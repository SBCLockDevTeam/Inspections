"""Isolated, admin-only PDF lifecycle API."""
import json
from fastapi import APIRouter, Body, Request, UploadFile, File
from fastapi.responses import JSONResponse, Response
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import object_session
from alarm_inspection.api.auth_support import require_admin
from alarm_inspection.api.common import UPLOAD_ROOT
from alarm_inspection.domain.pdf_integrations import IntegrationConfig
from alarm_inspection.integrations.pdf_feature import require_available
from alarm_inspection.integrations.pdf_files import PrivatePdfFiles
from alarm_inspection.integrations.pdf_models import PdfIntegration, PdfIntegrationVersion, PdfIntegrationAuditEntry
from alarm_inspection.integrations import pdf_repository as repo, pdf_service as service
from alarm_inspection.integrations.pdf_sources import configuration_source_catalog


def create_router(store):
    router=APIRouter(prefix='/api/admin/integrations',tags=['pdf-integrations'])
    files=PrivatePdfFiles(UPLOAD_ROOT)

    def run(request, operation):
        try:
            actor=require_admin(request)
            with store.begin() as session:
                repo._actor(session,actor.id,admin=True)
                result=operation(session,actor.id)
                return result if isinstance(result,Response) else JSONResponse(result)
        except PermissionError as exc: return JSONResponse({'error':str(exc)},status_code=403)
        except repo.ConflictError as exc: return JSONResponse({'error':str(exc),'code':'CONFLICT'},status_code=409)
        except (KeyError,TypeError) : return JSONResponse({'error':'Invalid or incomplete request.'},status_code=400)
        except (ValueError,ValidationError) as exc: return JSONResponse({'error':str(exc)},status_code=400)
        except (RuntimeError,OSError,SQLAlchemyError): return JSONResponse({'error':'PDF integrations are disabled or processing is unavailable.'},status_code=503)

    def version(row):
        session=object_session(row)
        audit=session.query(PdfIntegrationAuditEntry).filter(PdfIntegrationAuditEntry.version_id==row.id,
            PdfIntegrationAuditEntry.action.in_(['draft_created','draft_updated','version_sealed','publication_confirmed'])).order_by(PdfIntegrationAuditEntry.decided_at.desc(),PdfIntegrationAuditEntry.id.desc()).first()
        intake=session.query(PdfIntegrationAuditEntry).filter(PdfIntegrationAuditEntry.version_id==row.id,
            PdfIntegrationAuditEntry.action.in_(['template_intake','template_copied'])).first()
        return dict(template_filename=json.loads(intake.details_json).get('filename') if intake else 'Retained original template',
                    last_edited_by=audit.decided_by if audit else row.created_by,
                    id=row.id,key=row.integration_key,status=row.status,revision=row.revision,config_sha256=row.payload_sha256,
                    config=json.loads(row.payload_json),verification=json.loads(row.verification_json),
                    created_by=row.created_by,updated_at=row.updated_at.isoformat())

    @router.get('')
    def listing(request:Request):
        def operation(session,actor):
            return {'integrations':[dict(key=i.key,enabled=i.enabled,revision=i.revision,active_version_id=i.active_version_id,
                 versions=[version(v) for v in session.query(PdfIntegrationVersion).filter_by(integration_key=i.key).order_by(PdfIntegrationVersion.updated_at.desc())])
                 for i in session.query(PdfIntegration).order_by(PdfIntegration.key)]}
        return run(request,operation)

    @router.post('/{key}/templates')
    async def upload(key:str,request:Request,file:UploadFile=File(...)):
        # Authorize before reading untrusted input; bounded reads prevent RAM exhaustion.
        try: require_admin(request)
        except PermissionError as exc: return JSONResponse({'error':str(exc)},status_code=403)
        data=await file.read(40*1024**2+1); await file.close()
        return run(request,lambda s,a:version(service.intake(s,key,data,file.filename,files=files,actor_id=a)))

    @router.post('/versions/{ident}/copy')
    def copy(ident:str,request:Request): return run(request,lambda s,a:version(service.copy_draft(s,ident,files=files,actor_id=a)))

    @router.put('/versions/{ident}')
    def save(ident:str,request:Request,payload:dict=Body(...)):
        def operation(session,actor):
            config=IntegrationConfig.model_validate(payload['config'])
            if config.version_id!=ident: raise ValueError('Version identity mismatch.')
            revision=payload.get('expected_revision')
            if type(revision) is not int: raise ValueError('Expected revision is required.')
            repo.update_draft(session,config,files=files,actor_id=actor,expected_revision=revision)
            session.expire_all(); return version(repo._version(session,ident)[0])
        return run(request,operation)

    @router.get('/versions/{ident}/catalog')
    def catalog(ident:str,request:Request,inspection_id:str,panel_ids:str=''):
        return run(request,lambda s,a:configuration_source_catalog(store,inspection_id,ident,actor_id=a,panel_ids=panel_ids.split(',') if panel_ids else []))

    @router.get('/versions/{ident}/pages/{page}')
    def page(ident:str,page:int,request:Request):
        def operation(session,actor):
            _,config=repo._version(session,ident)
            if page not in config.inventory.selected_pages: raise ValueError('Excluded page.')
            data=service.bounded_pdf(files.read(config.original),config.inventory.selected_pages,'page',page=page)
            return Response(data,media_type='image/png',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        return run(request,operation)

    @router.post('/versions/{ident}/test')
    def test(ident:str,request:Request,payload:dict=Body(...)):
        def operation(session,actor):
            if type(payload.get('expected_revision')) is not int: raise ValueError('Expected revision required.')
            return service.test_draft(store,ident,payload.get('inspection_id'),payload.get('panel_ids',[]),files=files,actor_id=actor,expected_revision=payload['expected_revision'])
        return run(request,operation)

    @router.get('/tests/{ident}')
    def download(ident:str,request:Request):
        def operation(session,actor):
            row=repo._artifact(session,ident,actor)
            if row.purpose!='test': raise ValueError('Only diagnostic documents are available here.')
            return Response(repo.read_artifact(session,ident,files=files,actor_id=actor),media_type='application/pdf',headers={'Cache-Control':'no-store'})
        return run(request,operation)

    @router.post('/versions/{ident}/publish')
    def publish(ident:str,request:Request,payload:dict=Body(...)):
        def operation(session,actor):
            if payload.get('confirmed') is not True or not str(payload.get('change_summary','')).strip(): raise ValueError('Confirm publication and provide a change summary.')
            if type(payload.get('expected_revision')) is not int or type(payload.get('integration_revision')) is not int: raise ValueError('Expected version and integration revisions are required.')
            catalog=configuration_source_catalog(store,payload.get('inspection_id'),ident,actor_id=actor,panel_ids=payload.get('panel_ids',[]))
            service.publish(session,ident,files=files,actor_id=actor,expected_revision=payload.get('expected_revision'),
                test_artifact_id=payload.get('test_artifact_id'),verified_target_ids=payload.get('verified_target_ids',[]),catalog=catalog)
            row,config=repo._version(session,ident)
            repo.activate_version(session,config.integration_key,ident,expected_revision=payload.get('integration_revision'),actor_id=actor)
            repo._audit(session,config.integration_key,ident,'publication_confirmed',actor,{'summary':str(payload['change_summary'])[:1000]})
            return version(row)
        return run(request,operation)

    @router.post('/{key}/state')
    def state(key:str,request:Request,payload:dict=Body(...)):
        def operation(session,actor):
            if type(payload.get('expected_revision')) is not int: raise ValueError('Expected revision required.')
            if 'version_id' in payload: repo.activate_version(session,key,payload['version_id'],expected_revision=payload['expected_revision'],actor_id=actor)
            elif type(payload.get('enabled')) is bool: repo.set_enabled(session,key,payload['enabled'],expected_revision=payload['expected_revision'],actor_id=actor)
            else: raise ValueError('Choose a version or explicit enablement.')
            return {'status':'updated'}
        return run(request,operation)
    @router.post('/maintenance/expired-previews')
    def cleanup(request:Request):
        from alarm_inspection.integrations.pdf_exports import cleanup_expired_previews
        return run(request,lambda s,a:cleanup_expired_previews(store,files=files,actor_id=a))

    return router
