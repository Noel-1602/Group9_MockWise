from fastapi import FastAPI

app = FastAPI(
    title="MockWise API",
    description="Speech-to-Speech AI Mock Interview Platform",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}
