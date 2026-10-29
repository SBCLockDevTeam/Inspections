"""Authorized saved Form Details and readiness. Final exports are a later phase."""
from fastapi import APIRouter, Request, Body
from fastapi.responses import JSONResponse, Response
from alarm_inspection.api.common import UPLOAD_ROOT
from alarm_inspection.integrations.pdf_files import PrivatePdfFiles
from alarm_inspection.integrations import pdf_exports
from sqlalchemy.exc import SQLAlchemyError
from alarm_inspection.integrations import pdf_details
from alarm_inspection.integrations.pdf_repository import ConflictError


def create_router(store):
    files=PrivatePdfFiles(UPLOAD_ROOT)
    router=APIRouter(prefix='/api/inspections/{inspection_id}/form-integrations',tags=['form-details'])

    def run(request,operation):
        try:
            actor=getattr(request.state,'current_user',None)
            if actor is None: raise PermissionError('Authentication required.')
            result=operation(actor.id)
            return result if isinstance(result,Response) else JSONResponse(result,headers={'Cache-Control':'no-store'})
        except PermissionError as exc:return JSONResponse({'error':str(exc)},status_code=403)
        except pdf_exports.ExportBlocked as exc:return JSONResponse({'error':str(exc),'blockers':exc.blockers},status_code=422)
        except ConflictError as exc:return JSONResponse({'error':str(exc),'code':'CONFLICT'},status_code=409)
        except (ValueError,TypeError,KeyError) as exc:return JSONResponse({'error':str(exc)},status_code=400)
        except (RuntimeError,OSError,SQLAlchemyError):return JSONResponse({'error':'Form integrations are disabled or temporarily unavailable.'},status_code=503)

    def key_check(key):
        if key not in {'nfpa72','compliance'}:raise ValueError('Unknown integration.')
        return key

    @router.get('')
    def read(inspection_id:str,request:Request):
        return run(request,lambda actor:{'integrations':[pdf_details.details(store,inspection_id,key,actor_id=actor) for key in ('nfpa72','compliance')]})

    @router.get('/{key}')
    def read_one(inspection_id:str,key:str,request:Request):
        return run(request,lambda actor:pdf_details.details(store,inspection_id,key_check(key),actor_id=actor))

    @router.put('/{key}/scope')
    def scope(inspection_id:str,key:str,request:Request,payload:dict=Body(...)):
        return run(request,lambda actor:pdf_details.save_scope(store,inspection_id,key_check(key),payload,actor_id=actor))

    @router.put('/{key}/answers')
    def answer(inspection_id:str,key:str,request:Request,payload:dict=Body(...)):
        return run(request,lambda actor:pdf_details.save_answer(store,inspection_id,key_check(key),payload,actor_id=actor))
    @router.post('/{key}/preview')
    def preview(inspection_id:str,key:str,request:Request,payload:dict=Body(...)):
        return run(request,lambda actor:pdf_exports.preview(store,inspection_id,key_check(key),pdf_exports.PreviewRequest.model_validate(payload),files=files,actor_id=actor))

    @router.post('/{key}/exports')
    def confirm(inspection_id:str,key:str,request:Request,payload:dict=Body(...)):
        return run(request,lambda actor:pdf_exports.confirm(store,inspection_id,key_check(key),pdf_exports.ConfirmationRequest.model_validate(payload),files=files,actor_id=actor))

    @router.get('/{key}/exports')
    def history(inspection_id:str,key:str,request:Request):
        return run(request,lambda actor:pdf_exports.history(store,inspection_id,key_check(key),actor_id=actor))

    @router.get('/{key}/exports/{ident}/download')
    def download(inspection_id:str,key:str,ident:str,request:Request):
        def operation(actor):
            data,info=pdf_exports.download(store,inspection_id,key_check(key),ident,files=files,actor_id=actor)
            return Response(data,media_type='application/pdf',headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
                'Content-Disposition':f'{"inline" if info["purpose"]=="preview" else "attachment"}; filename="{info["filename"]}"'})
        return run(request,operation)

    @router.get('/{key}/exports/{ident}/provenance')
    def provenance(inspection_id:str,key:str,ident:str,request:Request):
        return run(request,lambda actor:pdf_exports.provenance(store,inspection_id,key_check(key),ident,actor_id=actor))

    @router.post('/{key}/exports/{ident}/recover')
    def recover(inspection_id:str,key:str,ident:str,request:Request):
        return run(request,lambda actor:pdf_exports.recover(store,inspection_id,key_check(key),ident,files=files,actor_id=actor))

    return router
