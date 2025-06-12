# cors.py
from fastapi.middleware.cors import CORSMiddleware


def add_cors(app):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",  # 개발용
            "https://arc.baeksung.kr",  # 배포용
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
