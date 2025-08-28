from datetime import datetime
from typing import Any, Dict
from pydantic import BaseModel, model_serializer
from utils.time import utc_to_kst_naive


class BaseResponse(BaseModel):
    """모든 Response 모델의 기본 클래스"""
    
    @model_serializer
    def serialize_model(self) -> Dict[str, Any]:
        """_at으로 끝나는 datetime 필드들을 자동으로 UTC → KST 변환"""
        data = {}
        
        for field_name, field_value in self.__dict__.items():
            if field_name.startswith('_'):
                continue
                
            # _at으로 끝나는 datetime 필드는 UTC → KST 변환
            if field_name.endswith('_at') and isinstance(field_value, datetime):
                kst_dt = utc_to_kst_naive(field_value)
                data[field_name] = kst_dt.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3]
            else:
                data[field_name] = field_value
                
        return data